#!/usr/bin/env python3
"""
Simple demonstration of the Pydantic configuration benefits without project validation.
"""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class SimpleToolConfig(BaseSettings):
    """Simple configuration example showing Pydantic benefits"""
    
    model_config = SettingsConfigDict(
        env_prefix="TOOL_",
        env_file=".env",
        case_sensitive=False
    )
    
    # Automatic type conversion and validation
    api_key: Optional[str] = Field(default=None, description="API key for service")
    timeout: int = Field(default=30, ge=1, le=300, description="Timeout in seconds")
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    verbose: bool = Field(default=False, description="Enable verbose output")
    output_format: str = Field(default="json", pattern="^(json|yaml|text)$")
    
    # Complex types with validation
    allowed_extensions: list[str] = Field(
        default=["py", "yaml", "toml", "json"],
        description="Allowed file extensions"
    )
    
    @field_validator("api_key")
    def validate_api_key(cls, v: Optional[str]) -> Optional[str]:
        """Custom validation for API key"""
        if v and not v.startswith(("sk-", "pk-", "test-")):
            raise ValueError("API key must start with sk-, pk-, or test-")
        return v


def main():
    print("🔧 Pydantic Configuration Benefits Demo\n")
    
    # 1. Type safety and validation
    print("1️⃣ Type Safety & Validation")
    print("-" * 40)
    
    try:
        # This will fail validation
        bad_config = SimpleToolConfig(timeout=500)  # Max is 300
    except ValidationError as e:
        print(f"✅ Validation caught error: {e.errors()[0]['msg']}")
    
    # This will succeed
    good_config = SimpleToolConfig(timeout=60, max_retries=5)
    print(f"✅ Valid config: timeout={good_config.timeout}s, retries={good_config.max_retries}")
    
    # 2. Automatic type conversion
    print("\n2️⃣ Automatic Type Conversion")
    print("-" * 40)
    
    # Set string env vars
    os.environ["TOOL_TIMEOUT"] = "45"  # String will convert to int
    os.environ["TOOL_VERBOSE"] = "true"  # String will convert to bool
    os.environ["TOOL_MAX_RETRIES"] = "7"
    
    config = SimpleToolConfig()
    print(f"✅ Converted from env vars:")
    print(f"   timeout: '{os.environ['TOOL_TIMEOUT']}' → {config.timeout} (type: {type(config.timeout).__name__})")
    print(f"   verbose: '{os.environ['TOOL_VERBOSE']}' → {config.verbose} (type: {type(config.verbose).__name__})")
    print(f"   max_retries: '{os.environ['TOOL_MAX_RETRIES']}' → {config.max_retries}")
    
    # 3. IDE support and documentation
    print("\n3️⃣ IDE Support & Documentation")
    print("-" * 40)
    print("✅ All fields have:")
    print("   • Type hints for auto-completion")
    print("   • Descriptions for documentation")
    print("   • Validation rules enforced")
    
    # Show field info
    for field_name, field_info in SimpleToolConfig.model_fields.items():
        constraints = []
        if hasattr(field_info, 'ge') and field_info.ge is not None:
            constraints.append(f"min={field_info.ge}")
        if hasattr(field_info, 'le') and field_info.le is not None:
            constraints.append(f"max={field_info.le}")
        constraint_str = f" ({', '.join(constraints)})" if constraints else ""
        print(f"   • {field_name}: {field_info.annotation}{constraint_str}")
    
    # 4. Configuration sources
    print("\n4️⃣ Multiple Configuration Sources")
    print("-" * 40)
    
    # Create a config with mixed sources
    config = SimpleToolConfig(
        # From code
        verbose=True,
        # From env vars (already set above)
        # timeout and max_retries come from env
    )
    
    print("✅ Configuration merged from:")
    print(f"   • Code: verbose={config.verbose}")
    print(f"   • Env vars: timeout={config.timeout}, max_retries={config.max_retries}")
    print(f"   • Defaults: output_format='{config.output_format}'")
    
    # 5. Export configuration
    print("\n5️⃣ Easy Serialization")
    print("-" * 40)
    
    config_dict = config.model_dump()
    print("✅ Export to dict:")
    print(f"   {config_dict}")
    
    config_json = config.model_dump_json(indent=2)
    print("\n✅ Export to JSON:")
    print(f"   {config_json}")
    
    # Clean up
    for key in ["TOOL_TIMEOUT", "TOOL_VERBOSE", "TOOL_MAX_RETRIES"]:
        if key in os.environ:
            del os.environ[key]
    
    print("\n✨ Benefits Summary:")
    print("• Type safety prevents runtime errors")
    print("• Automatic validation catches issues early")
    print("• Environment variable support built-in")
    print("• IDE auto-completion and type hints")
    print("• Easy serialization for configs")
    print("• Self-documenting with descriptions")


if __name__ == "__main__":
    main()