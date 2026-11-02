# Environment tools

Use generate_secrets.py only to create a NEW reviewed profile; it never overwrites existing files. validate_environment.sh validates inside the intended container and checks connectivity. See root ENVIRONMENT_VARIABLES.md, SECURITY_CONFIGURATION.md and PRODUCTION_DEPLOYMENT.md for alias handling, mounted secret files, restricted database roles and rotation.

For existing mounted-secret PermissionError, run deploy/check_secret_permissions.sh and apply the reviewed repair with --apply. Only direct, configured files under the project's secrets/ directory are eligible. Missing secrets are never regenerated. Host directory mode is 0700; individual mounted files are 0444 so differing non-root container UIDs can read only the files explicitly mounted into their service.
