# Troubleshooting

## Troubleshoot Dependency Installation

If any problems occur during the installation of dependencies, make sure
to check the following:

- Python version is 3.13 or higher
- You are running the command inside the virtual environment created in
  [Installing dependencies](install-manual.md#installing-dependencies)
- The `pyproject.toml` file is located in the project root directory
- The `uv` command is installed and working correctly (`uv --version`)
- The `uv` command is not blocked by any firewall or antivirus software
- The internet connection is stable and working correctly

## Troubleshoot Running Migrations

If any problems occur during the migration process, make sure to check
the following:

- The database is set up correctly and the user has all the necessary
  privileges
- The database connection is set up correctly in the `.env` file
- Each django app has a `migrations` directory with the `__init__.py` file
  and the migration files
- The database connection is working correctly
- The database is running and accessible
- The database is not blocked by any firewall or antivirus software
- The database is not corrupted or missing any necessary extensions
  (`could not open extension control file` for `vector` means the pgvector
  package is not installed; `permission denied to create extension` means the
  extensions must be created by the `postgres` superuser first, see
  [Setting up PostgreSQL](install-manual.md#setting-up-postgresql))
- The database is not missing any necessary configuration
