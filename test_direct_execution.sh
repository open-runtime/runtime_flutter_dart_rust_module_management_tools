#!/bin/bash
# Test script to verify direct execution of CLI tools

echo "Testing direct execution of CLI tools..."
echo ""

# Test a simple command
echo "Testing get_new_patch_tag.py directly:"
python3 tooling/cli/get_new_patch_tag.py --help

echo ""
echo "Testing with package import:"
python3 -m tooling.cli.get_new_patch_tag --help

echo ""
echo "Done! If both commands showed help text, the setup is working correctly."
