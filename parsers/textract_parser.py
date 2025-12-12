"""
AWS Textract parser for scanned and image-heavy PDFs.
Requires AWS credentials and incurs costs per page.
"""
import os
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dotenv import load_dotenv
from .base_parser import BaseParser, ParsedDocument

load_dotenv()


class TextractParser(BaseParser):
    """Parser using AWS Textract for OCR and document analysis."""
    
    def __init__(self):
        super().__init__("textract")
        try:
            import boto3
            self.boto3 = boto3
        except ImportError:
            raise ImportError(
                "boto3 is not installed. "
                "Install it with: pip install boto3"
            )
    
    def _get_region(self) -> str:
        """
        Get AWS region from environment variable or use default.
        
        Returns:
            AWS region name (default: us-east-1)
        """
        return os.getenv('AWS_REGION', os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))
    
    def is_available(self) -> bool:
        """
        Check if AWS Textract is available (credentials configured).
        
        Returns:
            True if AWS credentials are configured, False otherwise
        """
        try:
            import boto3
            from botocore.exceptions import NoCredentialsError, ClientError
            
            # Get region
            region = self._get_region()
            
            # Try to create a Textract client
            try:
                textract = boto3.client('textract', region_name=region)
                # Try a simple operation to verify credentials
                # We'll just check if we can create the client
                return True
            except (NoCredentialsError, ClientError) as e:
                # Check if it's a region error
                if 'region' in str(e).lower():
                    return False
                return False
        except Exception:
            return False
    
    def can_parse(self, file_path: str) -> bool:
        """Check if this parser can handle PDF files."""
        _, ext = os.path.splitext(file_path.lower())
        return ext == '.pdf' and self.is_available()
    
    def parse(self, file_path: str, file_content: Optional[bytes] = None) -> ParsedDocument:
        """
        Parse PDF using AWS Textract.
        
        Args:
            file_path: Path to PDF file
            file_content: Optional file content as bytes
        
        Returns:
            ParsedDocument with extracted text and metadata
        
        Note:
            This method incurs AWS costs. Each page processed costs money.
        """
        if not self.is_available():
            region = self._get_region()
            raise ValueError(
                f"AWS Textract is not available. "
                f"Please check:\n"
                f"1. AWS credentials are configured (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)\n"
                f"2. AWS region is set (AWS_REGION={region})\n"
                f"3. boto3 is installed: pip install boto3"
            )
        
        try:
            import boto3
            from botocore.exceptions import ClientError
            
            # Get region from environment or use default
            region = self._get_region()
            
            # Initialize Textract client with region and timeout
            # Use config to set timeout for API calls
            from botocore.config import Config
            config = Config(
                connect_timeout=10,  # 10 seconds to connect
                read_timeout=30,     # 30 seconds to read response
                retries={'max_attempts': 1}  # Don't retry on timeout
            )
            textract = boto3.client('textract', region_name=region, config=config)
            
            # Prepare document
            if file_content:
                # Use bytes
                document = {'Bytes': file_content}
            else:
                # Use file path (Textract can read from S3 or local file)
                # For local files, we need to read and send as bytes
                with open(file_path, 'rb') as f:
                    document = {'Bytes': f.read()}
            
            # Call Textract with timeout using ThreadPoolExecutor
            # This prevents UI freezing if Textract hangs
            def call_textract():
                return textract.detect_document_text(Document=document)
            
            # Use ThreadPoolExecutor with timeout to prevent UI freezing
            timeout_seconds = 45  # 45 second timeout for Textract
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(call_textract)
                try:
                    response = future.result(timeout=timeout_seconds)
                except FutureTimeoutError:
                    raise ValueError(
                        f"Textract parsing timed out after {timeout_seconds} seconds. "
                        f"The document may be too large or the service is slow. "
                        f"Falling back to PyMuPDF parser."
                    )
                except Exception as e:
                    raise ValueError(f"Textract API call failed: {str(e)}")
            
            # Extract text from response
            text_parts = []
            pages = set()
            
            for block in response.get('Blocks', []):
                if block['BlockType'] == 'PAGE':
                    pages.add(block.get('Page', 1))
                elif block['BlockType'] == 'LINE':
                    text_parts.append(block.get('Text', ''))
            
            full_text = '\n'.join(text_parts)
            total_pages = len(pages) if pages else 1
            
            # Textract is good at OCR, so high confidence
            confidence = 0.95 if len(full_text.strip()) > 100 else 0.7
            extraction_percentage = 1.0 if len(full_text.strip()) > 100 else 0.0
            
            # Check for images (Textract processes images, so they're detected)
            images_detected = len(full_text.strip()) > 0  # If we got text, images were processed
            
            # Calculate cost estimate (approximate)
            # Textract pricing: ~$1.50 per 1000 pages for standard text detection
            estimated_cost = total_pages * 0.0015  # Rough estimate
            
            metadata = {
                "source": file_path,
                "pages": total_pages,
                "text_length": len(full_text),
                "estimated_cost_usd": estimated_cost,
                "file_size": len(file_content) if file_content else os.path.getsize(file_path)
            }
            
            return ParsedDocument(
                text=full_text,
                metadata=metadata,
                pages=total_pages,
                images_detected=images_detected,
                parser_used=self.name,
                confidence=confidence,
                extraction_percentage=extraction_percentage,
                image_count=0  # Textract processes images but doesn't count them separately
            )
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = str(e)
            
            # Provide helpful error messages
            if 'region' in error_msg.lower():
                region = self._get_region()
                raise ValueError(
                    f"AWS Textract region error: {error_msg}\n"
                    f"Current region: {region}\n"
                    f"Please set AWS_REGION in your .env file or environment variables."
                )
            elif 'credentials' in error_msg.lower() or 'UnauthorizedOperation' in error_code:
                raise ValueError(
                    f"AWS Textract authentication error ({error_code}): {error_msg}\n"
                    f"Please check your AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)."
                )
            else:
                raise ValueError(f"AWS Textract error ({error_code}): {error_msg}")
        except Exception as e:
            error_msg = str(e)
            if 'region' in error_msg.lower():
                region = self._get_region()
                raise ValueError(
                    f"Failed to parse PDF with Textract: {error_msg}\n"
                    f"Please set AWS_REGION in your .env file (current: {region})."
                )
            raise ValueError(f"Failed to parse PDF with Textract: {error_msg}")

