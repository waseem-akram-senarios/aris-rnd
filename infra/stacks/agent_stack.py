"""
ARIS Agent ECS Stack for AWS CDK.

Deploys ARIS services to existing ECS cluster intelycx-dev-cluster.
"""
from typing import Dict, List, Any, Optional

from aws_cdk import (
    Stack,
    CfnOutput,
    RemovalPolicy,
    Duration,
    Annotations,
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_elasticloadbalancingv2 as elbv2,
    aws_logs as logs,
    aws_secretsmanager as secretsmanager,
    aws_ssm as ssm,
    aws_servicediscovery as servicediscovery,
)
from constructs import Construct


class AgentStack(Stack):
    """CDK Stack for deploying ARIS services to ECS."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Store region and account for later use (CDK Stack.region/account are read-only properties)
        # Read from the properties and store in separate variables for boto3 calls
        region_value = getattr(self, 'region', None)
        account_value = getattr(self, 'account', None)
        self.stack_region = region_value if region_value else "us-east-2"
        self.stack_account = account_value if account_value else "975049910508"

        env_name = self.node.try_get_context("env") or "dev"
        cluster_name = self.node.try_get_context("cluster_name") or "intelycx-dev-cluster"
        
        # Database configuration
        self.database_host = self.node.try_get_context("database_host") or f"aris-postgres-{env_name}"
        
        # VPC and networking configuration (from existing cluster)
        vpc_id = self.node.try_get_context("vpc_id") or "vpc-0aad20b9963e29f38"
        subnet_ids = self.node.try_get_context("subnet_ids") or [
            "subnet-0835ed1aedb87026a",  # us-east-2b
            "subnet-0e3e46ca86701686b",  # us-east-2c
            "subnet-05c352570f5e8128c",  # us-east-2a
        ]
        security_group_id = self.node.try_get_context("security_group_id") or "sg-05cb45ca06004c701"
        alb_arn = self.node.try_get_context("alb_arn") or "arn:aws:elasticloadbalancing:us-east-2:975049910508:loadbalancer/app/intelycx-alb-dev/d03a8658af509291"

        # Import existing VPC and networking resources
        self.vpc = ec2.Vpc.from_lookup(self, "Vpc", vpc_id=vpc_id)
        self.subnets = [ec2.Subnet.from_subnet_id(self, f"Subnet{i}", subnet_id=sid) for i, sid in enumerate(subnet_ids)]
        self.security_group = ec2.SecurityGroup.from_security_group_id(
            self, "EcsSecurityGroup", security_group_id=security_group_id
        )
        
        # Get ALB security group from context or use default
        alb_security_group_id = self.node.try_get_context("alb_security_group_id") or "sg-0bbdbdf305674fe64"
        alb_security_group = ec2.SecurityGroup.from_security_group_id(
            self, "AlbSecurityGroup", security_group_id=alb_security_group_id
        )
        
        # Add ingress rule for PostgreSQL (port 5432) within the security group
        # This allows services to connect to PostgreSQL
        self.security_group.add_ingress_rule(
            peer=self.security_group,
            connection=ec2.Port.tcp(5432),
            description="Allow PostgreSQL connections within security group"
        )
        
        # Add ingress rules for ALB to reach ECS tasks on service ports
        # This allows ALB health checks and traffic routing
        service_ports = [443, 8080, 8081, 8082]  # Agent (443), Core (8080), Email (8081), RAG (8082), FileGen (8080)
        for port in service_ports:
            self.security_group.add_ingress_rule(
                peer=alb_security_group,
                connection=ec2.Port.tcp(port),
                description=f"Allow ALB traffic on port {port}"
            )

        # Import existing ECS cluster
        self.cluster = ecs.Cluster.from_cluster_attributes(
            self,
            "Cluster",
            cluster_name=cluster_name,
            vpc=self.vpc,
            security_groups=[self.security_group],
        )

        # Import existing ALB for listener rule creation
        self.alb_arn = alb_arn
        # Note: We'll look up the ALB listeners during service creation
        # to automatically add routing rules

        # Create ECR repositories for ARIS services
        self.ecr_repos = self._create_ecr_repositories(env_name)

        # Create IAM execution role for ECS tasks
        self.execution_role = self._create_execution_role(env_name)
        
        # Create task roles for each service
        self.task_roles = self._create_task_roles(env_name)

        # Create secrets for sensitive configuration
        self.secrets = self._create_secrets(env_name)

        # Create CloudWatch log groups
        self.log_groups = self._create_log_groups(env_name)

        # Create service discovery namespace for internal service communication
        self.namespace = self._create_service_discovery_namespace(env_name)

        # Create PostgreSQL service first (other services depend on it)
        self.postgres_service = self._create_postgres_service(env_name)

        # Create ECS services
        self.services = self._create_ecs_services(env_name)

        # Outputs
        CfnOutput(self, "ClusterName", value=cluster_name)
        CfnOutput(self, "VpcId", value=vpc_id)
        for service_name, service in self.services.items():
            CfnOutput(self, f"{service_name}ServiceArn", value=service.service_arn)

    def _create_ecr_repositories(self, env_name: str) -> Dict[str, ecr.Repository]:
        """Import existing ECR repositories for ARIS services."""
        repos = {}
        service_names = [
            "aris-agent",
            "aris-mcp-intelycx-core",
            "aris-mcp-intelycx-email",
            "aris-mcp-intelycx-file-generator",
            "aris-mcp-intelycx-rag",
        ]
        
        for service_name in service_names:
            repo_name = f"{service_name}-{env_name}"
            # Import existing repository (created when pushing Docker images)
            repos[service_name] = ecr.Repository.from_repository_name(
                self,
                f"{service_name.replace('-', '').replace('_', '')}Repo",
                repository_name=repo_name,
            )
        
        return repos

    def _create_execution_role(self, env_name: str) -> iam.Role:
        """Create IAM role for ECS task execution."""
        role = iam.Role(
            self,
            "EcsExecutionRole",
            role_name=f"intelycx-aris-{env_name}-execution-role",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
            ],
        )

        # Grant ECR pull permissions
        for repo in self.ecr_repos.values():
            repo.grant_pull(role)

        # Grant CloudWatch Logs permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=["*"],
            )
        )

        # Grant Secrets Manager access
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret",
                ],
                resources=["*"],  # Will be scoped to specific secrets in production
            )
        )

        # Grant SSM Parameter Store access
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:GetParameter",
                    "ssm:GetParameters",
                    "ssm:GetParametersByPath",
                ],
                resources=[
                    f"arn:aws:ssm:{self.stack_region}:{self.stack_account}:parameter/intelycx-aris-{env_name}/*"
                ],
            )
        )

        return role

    def _create_task_roles(self, env_name: str) -> Dict[str, iam.Role]:
        """Create IAM roles for ECS tasks (application permissions)."""
        roles = {}
        
        # Common task role for all services
        common_role = iam.Role(
            self,
            "EcsTaskRole",
            role_name=f"intelycx-aris-{env_name}-task-role",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        # Grant S3 access
        common_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                ],
                resources=[
                    f"arn:aws:s3:::iris-batch-001-data-{self.stack_account}",
                    f"arn:aws:s3:::iris-batch-001-data-{self.stack_account}/*",
                ],
            )
        )

        # Grant Bedrock access
        common_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:Converse",
                ],
                resources=["*"],
            )
        )

        # Grant SES access for email service
        common_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ses:SendEmail",
                    "ses:SendRawEmail",
                ],
                resources=["*"],
            )
        )

        # Grant OpenSearch access (if needed)
        common_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "es:ESHttpGet",
                    "es:ESHttpPost",
                    "es:ESHttpPut",
                    "aoss:APIAccessAll",
                ],
                resources=["*"],
            )
        )

        # Use same role for all services (can be customized per service if needed)
        for service_name in self.ecr_repos.keys():
            roles[service_name] = common_role

        return roles

    def _create_secrets(self, env_name: str) -> Dict[str, secretsmanager.Secret]:
        """Import existing AWS Secrets Manager secrets for sensitive configuration."""
        secrets = {}
        
        # Import existing database password secret
        secrets["database"] = secretsmanager.Secret.from_secret_name_v2(
            self,
            "DatabaseSecret",
            secret_name=f"intelycx-aris-{env_name}-database",
        )

        # Import existing AWS credentials secret
        secrets["aws_credentials"] = secretsmanager.Secret.from_secret_name_v2(
            self,
            "AwsCredentialsSecret",
            secret_name=f"intelycx-aris-{env_name}-aws-credentials",
        )

        return secrets

    def _create_log_groups(self, env_name: str) -> Dict[str, logs.LogGroup]:
        """Create CloudWatch log groups for services."""
        log_groups = {}
        
        for service_name in self.ecr_repos.keys():
            log_group_name = f"/ecs/intelycx-aris-{env_name}/{service_name}"
            log_groups[service_name] = logs.LogGroup(
                self,
                f"{service_name.replace('-', '').replace('_', '')}LogGroup",
                log_group_name=log_group_name,
                retention=logs.RetentionDays.ONE_MONTH,
                removal_policy=RemovalPolicy.DESTROY,
            )
        
        return log_groups

    def _create_service_discovery_namespace(self, env_name: str) -> servicediscovery.PrivateDnsNamespace:
        """Create Cloud Map namespace for service discovery."""
        return servicediscovery.PrivateDnsNamespace(
            self,
            "ServiceDiscoveryNamespace",
            name=f"aris-{env_name}.local",
            vpc=self.vpc,
            description=f"Service discovery namespace for ARIS {env_name} environment",
        )

    def _create_postgres_service(self, env_name: str) -> ecs.FargateService:
        """Create PostgreSQL ECS service with service discovery."""
        # Log group for PostgreSQL
        postgres_log_group = logs.LogGroup(
            self,
            "PostgresLogGroup",
            log_group_name=f"/ecs/intelycx-aris-{env_name}/aris-postgres",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Get database password from secrets
        db_secret = secretsmanager.Secret.from_secret_name_v2(
            self, "PostgresDbSecret", f"intelycx-aris-{env_name}-database"
        )

        # Task definition for PostgreSQL
        postgres_task_def = ecs.FargateTaskDefinition(
            self,
            "PostgresTaskDef",
            cpu=512,  # 0.5 vCPU
            memory_limit_mib=1024,  # 1 GB
            execution_role=self.execution_role,
            task_role=self.execution_role,  # PostgreSQL doesn't need special task role
        )

        # Container definition
        postgres_container = postgres_task_def.add_container(
            "PostgresContainer",
            image=ecs.ContainerImage.from_registry("postgres:16-alpine"),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="aris-postgres",
                log_group=postgres_log_group,
            ),
            environment={
                "POSTGRES_DB": "aris_agent",
                "POSTGRES_USER": "aris",
                "POSTGRES_INITDB_ARGS": "--encoding=UTF8 --lc-collate=C --lc-ctype=C",
            },
            secrets={
                "POSTGRES_PASSWORD": ecs.Secret.from_secrets_manager(
                    db_secret, field="password"
                ),
            },
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "pg_isready -U aris -d aris_agent"],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(60),
            ),
        )

        # Port mapping
        postgres_container.add_port_mappings(
            ecs.PortMapping(
                container_port=5432,
                protocol=ecs.Protocol.TCP,
            )
        )

        # Create ECS service with Cloud Map service discovery
        # Cloud Map service will be created automatically
        postgres_service = ecs.FargateService(
            self,
            "PostgresService",
            service_name=f"aris-postgres-{env_name}",
            cluster=self.cluster,
            task_definition=postgres_task_def,
            desired_count=1,  # Single instance for now
            vpc_subnets=ec2.SubnetSelection(subnets=self.subnets),
            security_groups=[self.security_group],
            assign_public_ip=False,
            health_check_grace_period=Duration.seconds(60),
            cloud_map_options=ecs.CloudMapOptions(
                name=f"aris-postgres-{env_name}",
                cloud_map_namespace=self.namespace,
            ),
        )

        # Update database host to use service discovery full DNS name
        # Cloud Map private DNS namespace format: service-name.namespace-name
        self.database_host = f"aris-postgres-{env_name}.aris-{env_name}.local"

        return postgres_service

    def _create_ecs_services(self, env_name: str) -> Dict[str, ecs.FargateService]:
        """Create ECS Fargate services for ARIS components."""
        services = {}
        
        # Service configurations
        service_configs = {
            "aris-agent": {
                "port": 443,
                "cpu": 1024,  # 1 vCPU
                "memory": 2048,  # 2 GB
                "desired_count": 2,
                "health_check_path": "/health",
            },
            "aris-mcp-intelycx-core": {
                "port": 8080,
                "cpu": 512,
                "memory": 1024,
                "desired_count": 2,
                "health_check_path": "/health",
            },
            "aris-mcp-intelycx-email": {
                "port": 8081,
                "cpu": 256,
                "memory": 512,
                "desired_count": 1,
                "health_check_path": "/health",
            },
            "aris-mcp-intelycx-file-generator": {
                "port": 8080,
                "cpu": 512,
                "memory": 1024,
                "desired_count": 1,
                "health_check_path": "/health",
            },
            "aris-mcp-intelycx-rag": {
                "port": 8082,
                "cpu": 1024,
                "memory": 2048,
                "desired_count": 1,
                "health_check_path": "/health",
            },
        }

        # Create target groups for ALB
        # Shorten service names for target groups (AWS limit: 32 chars)
        def get_short_tg_name(service_name: str, env_name: str) -> str:
            """Generate short target group name within 32 character limit."""
            # Map service names to shorter versions
            short_names = {
                "aris-agent": "agent",
                "aris-mcp-intelycx-core": "core",
                "aris-mcp-intelycx-email": "email",
                "aris-mcp-intelycx-file-generator": "filegen",
                "aris-mcp-intelycx-rag": "rag",
            }
            short_name = short_names.get(service_name, service_name.replace("aris-mcp-intelycx-", "").replace("aris-", ""))
            tg_name = f"aris-{short_name}-{env_name}"
            # Ensure it's within 32 chars
            if len(tg_name) > 32:
                tg_name = tg_name[:32]
            return tg_name
        
        target_groups = {}
        for service_name, config in service_configs.items():
            target_groups[service_name] = elbv2.ApplicationTargetGroup(
                self,
                f"{service_name.replace('-', '').replace('_', '')}TargetGroup",
                target_group_name=get_short_tg_name(service_name, env_name),
                port=config["port"],
                protocol=elbv2.ApplicationProtocol.HTTP,
                vpc=self.vpc,
                target_type=elbv2.TargetType.IP,  # Required for Fargate with awsvpc network mode
                health_check=elbv2.HealthCheck(
                    path=config["health_check_path"],
                    interval=Duration.seconds(30),
                    timeout=Duration.seconds(5),
                    healthy_threshold_count=2,
                    unhealthy_threshold_count=3,
                ),
                deregistration_delay=Duration.seconds(30),
            )

        # Store target groups for ALB integration
        self.target_groups = target_groups

        # Create ALB listener rules FIRST to attach target groups to load balancer
        # This must happen before services attach to target groups
        service_listener_rules = self._create_alb_listener_rules(target_groups, env_name)

        # Create task definitions and services
        for service_name, config in service_configs.items():
            repo = self.ecr_repos[service_name]
            log_group = self.log_groups[service_name]
            task_role = self.task_roles[service_name]
            target_group = target_groups[service_name]

            # Task definition
            task_def = ecs.FargateTaskDefinition(
                self,
                f"{service_name.replace('-', '').replace('_', '')}TaskDef",
                cpu=config["cpu"],
                memory_limit_mib=config["memory"],
                execution_role=self.execution_role,
                task_role=task_role,
            )

            # Container definition
            container = task_def.add_container(
                f"{service_name}Container",
                image=ecs.ContainerImage.from_ecr_repository(repo, tag="latest"),
                logging=ecs.LogDrivers.aws_logs(
                    stream_prefix=service_name,
                    log_group=log_group,
                ),
                environment=self._get_environment_variables(service_name, env_name),
                secrets=self._get_secrets(service_name, env_name),
                health_check=ecs.HealthCheck(
                    command=["CMD-SHELL", f"curl -f http://localhost:{config['port']}{config['health_check_path']} || exit 1"],
                    interval=Duration.seconds(30),
                    timeout=Duration.seconds(5),
                    retries=3,
                    start_period=Duration.seconds(60),
                ),
            )

            # Port mapping
            container.add_port_mappings(
                ecs.PortMapping(
                    container_port=config["port"],
                    protocol=ecs.Protocol.TCP,
                )
            )

            # ECS Service
            service = ecs.FargateService(
                self,
                f"{service_name.replace('-', '').replace('_', '')}Service",
                service_name=f"{service_name}-{env_name}",
                cluster=self.cluster,
                task_definition=task_def,
                desired_count=config["desired_count"],
                vpc_subnets=ec2.SubnetSelection(subnets=self.subnets),
                security_groups=[self.security_group],
                assign_public_ip=False,  # Private subnets
                health_check_grace_period=Duration.seconds(60),
            )

            # Register service with target group
            # Target groups will be attached to ALB listeners via listener rules created above
            # Add dependency on listener rules to ensure target groups are associated with load balancer first
            listener_rules = service_listener_rules.get(service_name, [])
            if listener_rules:
                # Make service depend on at least one listener rule to ensure target group is associated
                service.node.add_dependency(listener_rules[0])
            service.attach_to_application_target_group(target_group)

            services[service_name] = service

        # Output target group ARNs for reference
        for service_name, target_group in target_groups.items():
            CfnOutput(
                self,
                f"{service_name.replace('-', '').replace('_', '')}TargetGroupArn",
                value=target_group.target_group_arn,
                description=f"Target group ARN for {service_name}",
            )

        return services

    def _create_alb_listener_rules(
        self, target_groups: Dict[str, elbv2.ApplicationTargetGroup], env_name: str
    ) -> Dict[str, List[elbv2.CfnListenerRule]]:
        """Create ALB listener rules to route traffic to ARIS services.
        
        Returns a dictionary mapping service names to their listener rules.
        """
        # Path patterns for routing (adjust based on your needs)
        path_patterns = {
            "aris-agent": ["/aris/agent/*", "/aris/ws/*"],  # WebSocket and API
            "aris-mcp-intelycx-core": ["/aris/core/*", "/aris/mcp/core/*"],
            "aris-mcp-intelycx-email": ["/aris/email/*", "/aris/mcp/email/*"],
            "aris-mcp-intelycx-file-generator": ["/aris/file/*", "/aris/mcp/file/*"],
            "aris-mcp-intelycx-rag": ["/aris/rag/*", "/aris/mcp/rag/*"],
        }

        # Get listener ARNs from context or look them up automatically
        http_listener_arn = self.node.try_get_context("http_listener_arn")
        https_listener_arn = self.node.try_get_context("https_listener_arn")
        
        # If not provided, try to look up listeners from the ALB
        if not http_listener_arn or not https_listener_arn:
            try:
                import boto3
                elbv2_client = boto3.client('elbv2', region_name=self.stack_region)
                listeners_response = elbv2_client.describe_listeners(
                    LoadBalancerArn=self.alb_arn
                )
                for listener in listeners_response.get('Listeners', []):
                    if listener['Port'] == 80 and not http_listener_arn:
                        http_listener_arn = listener['ListenerArn']
                    elif listener['Port'] == 443 and not https_listener_arn:
                        https_listener_arn = listener['ListenerArn']
            except Exception as e:
                Annotations.of(self).add_warning(f"Could not auto-discover listener ARNs: {e}. Please provide http_listener_arn and https_listener_arn in context.")

        # Store listener rules per service for dependency management
        service_listener_rules: Dict[str, List[elbv2.CfnListenerRule]] = {
            service_name: [] for service_name in target_groups.keys()
        }

        # Create rules for HTTP listener (port 80) using CloudFormation resources
        if http_listener_arn:
            priority = 100
            for service_name, target_group in target_groups.items():
                patterns = path_patterns.get(service_name, [f"/aris/{service_name.replace('aris-', '')}/*"])
                for pattern in patterns:
                    rule = elbv2.CfnListenerRule(
                        self,
                        f"{service_name.replace('-', '').replace('_', '')}HttpRule{priority}",
                        listener_arn=http_listener_arn,
                        priority=priority,
                        conditions=[
                            elbv2.CfnListenerRule.RuleConditionProperty(
                                field="path-pattern",
                                values=[pattern],
                            )
                        ],
                        actions=[
                            elbv2.CfnListenerRule.ActionProperty(
                                type="forward",
                                target_group_arn=target_group.target_group_arn,
                            )
                        ],
                    )
                    service_listener_rules[service_name].append(rule)
                    priority += 1
        else:
            Annotations.of(self).add_warning("HTTP listener ARN not provided - listener rules will need to be created manually")

        # Create rules for HTTPS listener (port 443) using CloudFormation resources
        if https_listener_arn:
            priority = 100
            for service_name, target_group in target_groups.items():
                patterns = path_patterns.get(service_name, [f"/aris/{service_name.replace('aris-', '')}/*"])
                for pattern in patterns:
                    rule = elbv2.CfnListenerRule(
                        self,
                        f"{service_name.replace('-', '').replace('_', '')}HttpsRule{priority}",
                        listener_arn=https_listener_arn,
                        priority=priority,
                        conditions=[
                            elbv2.CfnListenerRule.RuleConditionProperty(
                                field="path-pattern",
                                values=[pattern],
                            )
                        ],
                        actions=[
                            elbv2.CfnListenerRule.ActionProperty(
                                type="forward",
                                target_group_arn=target_group.target_group_arn,
                            )
                        ],
                    )
                    service_listener_rules[service_name].append(rule)
                    priority += 1
        else:
            Annotations.of(self).add_warning("HTTPS listener ARN not provided - listener rules will need to be created manually")
        
        return service_listener_rules

    def _get_environment_variables(self, service_name: str, env_name: str) -> Dict[str, str]:
        """Get environment variables for a service."""
        base_env = {
            "REGION": self.region,
            "AWS_DEFAULT_REGION": self.region,
            "AWS_REGION": self.region,
            "BEDROCK_REGION": self.region,
            "LOG_LEVEL": "INFO",
        }

        service_specific = {
            "aris-agent": {
                "AGENT_TYPE": "manufacturing",
                "HOST": "0.0.0.0",
                "PORT": "443",
                "INTELYCX_CORE_MCP_URL": f"http://aris-mcp-intelycx-core-{env_name}:8080",
                "INTELYCX_EMAIL_MCP_URL": f"http://aris-mcp-intelycx-email-{env_name}:8081",
                "DATABASE_URL": f"postgresql+asyncpg://aris:${{DB_PASSWORD}}@{self.database_host}:5432/aris_agent",
            },
            "aris-mcp-intelycx-core": {
                "HOST": "0.0.0.0",
                "PORT": "8080",
                "UVICORN_ACCESS_LOG": "false",
            },
            "aris-mcp-intelycx-email": {
                "HOST": "0.0.0.0",
                "PORT": "8081",
                "UVICORN_ACCESS_LOG": "false",
                "EMAIL_DRIVER": "ses",
                "EMAIL_REGION": self.region,
                "EMAIL_SENDER": "aris@intelycx.com",
                "EMAIL_SENDER_NAME": "Intelycx ARIS",
            },
            "aris-mcp-intelycx-file-generator": {
                "HOST": "0.0.0.0",
                "PORT": "8080",
                "STORAGE_DRIVER": "s3",
                "S3_BUCKET_NAME": f"iris-batch-001-data-{self.stack_account}",
            },
            "aris-mcp-intelycx-rag": {
                "HOST": "0.0.0.0",
                "PORT": "8082",
                "S3_DOCUMENT_BUCKET": f"iris-batch-001-data-{self.stack_account}",
                "EMBEDDING_MODEL": "amazon.titan-embed-text-v2:0",
                "EMBEDDING_DIMENSIONS": "1536",
                "DATABASE_URL": f"postgresql+asyncpg://aris:${{DB_PASSWORD}}@{self.database_host}:5432/aris_agent",
            },
        }

        return {**base_env, **service_specific.get(service_name, {})}

    def _get_secrets(self, service_name: str, env_name: str) -> Dict[str, ecs.Secret]:
        """Get secrets for a service from Secrets Manager."""
        secrets_dict = {}
        
        # Database password for services that need it
        if service_name in ["aris-agent", "aris-mcp-intelycx-rag"]:
            db_secret = secretsmanager.Secret.from_secret_name_v2(
                self, f"{service_name}DbSecret", f"intelycx-aris-{env_name}-database"
            )
            secrets_dict["DB_PASSWORD"] = ecs.Secret.from_secrets_manager(
                db_secret, field="password"
            )

        # MCP API key (could be stored in Secrets Manager)
        # For now, using environment variable - consider moving to secrets
        
        return secrets_dict
