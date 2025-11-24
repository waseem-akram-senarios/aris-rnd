# ARIS R&D - Changelog

## Latest Updates

### Answer Quality Improvements (Latest)
- **Fixed repetitive text issue**: Added answer cleaning to remove "Best regards", signatures, and repetitive phrases
- **Enhanced prompts**: Added explicit instructions to prevent hallucinations and unwanted endings
- **Stop sequences**: Added stop tokens to prevent LLM from generating unwanted text
- **Answer cleaning function**: Automatically removes unwanted greetings and signatures from answers

### Accuracy Improvements
- **Optimized chunking**: Reduced chunk size to 384 tokens (from 512) for better precision
- **Increased overlap**: 75 tokens overlap (from 50) for better context continuity
- **MMR retrieval**: Maximum Marginal Relevance for diverse, relevant chunks
- **More chunks**: Retrieve 6 chunks (from 4) for better coverage
- **Lower temperature**: 0.3 (from 0.7) for more deterministic answers
- **Better prompts**: Structured prompts with accuracy guidelines

### Project Naming
- **Project renamed**: "ARIS R&D" throughout the application
- Updated page titles, headers, and documentation

## Technical Details

### Answer Cleaning
The system now automatically:
- Removes "Best regards", "Thank you", and similar endings
- Stops at first unwanted phrase
- Removes repetitive patterns
- Cleans trailing unwanted text

### Prompt Improvements
- Explicit "DO NOT" instructions for unwanted text
- Stop sequences in API calls
- Post-processing cleanup function

