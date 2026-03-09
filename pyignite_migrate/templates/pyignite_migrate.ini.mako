[pyignite_migrate]
# Connection to Apache Ignite cluster (comma-separated host:port pairs)
hosts = 127.0.0.1:10800

# Path to migration scripts directory (relative to this file)
script_location = ${script_location}

# SQL schema for version tracking and migrations
schema = PUBLIC

# Name of the version tracking table
version_table = __pyignite_migrate_version

# File naming template
file_template = ${"${rev}_${slug}"}
