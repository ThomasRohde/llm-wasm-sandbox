"""
Data Transformation Examples with sandbox_utils

This module demonstrates data processing and transformation workflows using
utilities from the sandbox_utils library. All operations run within the /app sandbox.

Examples include:
- CSV to JSON conversion
- Data aggregation and grouping
- Report generation with tabulate
- Multi-format data processing
"""

from sandbox import RuntimeType, create_sandbox


def demo_csv_json_conversion():
    """Example: Convert between CSV and JSON formats."""
    print("\n" + "=" * 60)
    print("DEMO: CSV to JSON Conversion")
    print("=" * 60)

    code = """
from sandbox_utils import csv_to_json, json_to_csv, echo, cat, mkdir
import json

# Create sample CSV data
mkdir("/app/data", parents=True)

employees_csv = '''id,name,department,salary,hire_date
101,Alice Johnson,Engineering,95000,2020-03-15
102,Bob Smith,Engineering,87000,2021-06-01
103,Charlie Brown,Sales,92000,2019-11-20
104,Diana Prince,Engineering,105000,2018-08-10
105,Eve Wilson,Sales,78000,2022-01-05
106,Frank Miller,HR,65000,2020-09-12
107,Grace Lee,Engineering,98000,2021-03-22
108,Henry Davis,Sales,85000,2020-12-01'''

echo(employees_csv, "/app/data/employees.csv")

print("=== CSV TO JSON CONVERSION ===\\n")
print("Original CSV:")
print(cat("/app/data/employees.csv"))

# Convert CSV to JSON
json_output = csv_to_json("/app/data/employees.csv", output="/app/data/employees.json")
print("\\n✓ Converted to JSON\\n")

# Display JSON (pretty-printed)
with open("/app/data/employees.json", 'r') as f:
    data = json.load(f)

print(f"Total records: {len(data)}\\n")
print("First 3 records:")
for record in data[:3]:
    print(f"  {record['id']}: {record['name']:20s} - {record['department']:12s} - ${record['salary']}")

# Convert back to CSV
print("\\n=== JSON TO CSV CONVERSION ===\\n")
csv_output = json_to_csv("/app/data/employees.json", output="/app/data/employees_copy.csv")
print("✓ Converted back to CSV\\n")

print("Regenerated CSV:")
print(cat("/app/data/employees_copy.csv"))

# Verify data integrity
original_lines = cat("/app/data/employees.csv").strip().split('\\n')
copy_lines = cat("/app/data/employees_copy.csv").strip().split('\\n')

if len(original_lines) == len(copy_lines):
    print(f"\\n✓ Data integrity verified: {len(original_lines)} rows preserved")
else:
    print(f"\\n⚠ Data mismatch: {len(original_lines)} vs {len(copy_lines)} rows")
"""

    sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
    result = sandbox.execute(code)

    print(result.stdout)
    print(f"\n[Fuel consumed: {result.fuel_consumed:,} instructions]")


def demo_data_aggregation():
    """Example: Aggregate and analyze data using functional utilities."""
    print("\n" + "=" * 60)
    print("DEMO: Data Aggregation and Analysis")
    print("=" * 60)

    code = """
from sandbox_utils import csv_to_json, group_by, filter_by, sort_by, echo, mkdir
import json

# Create sales data
mkdir("/app/sales", parents=True)

sales_csv = '''date,product,category,quantity,revenue,region
2024-11-01,Laptop,Electronics,5,4500,North
2024-11-01,Mouse,Electronics,20,400,North
2024-11-01,Desk,Furniture,3,900,South
2024-11-02,Chair,Furniture,8,1600,North
2024-11-02,Laptop,Electronics,3,2700,South
2024-11-02,Monitor,Electronics,7,2100,East
2024-11-03,Desk,Furniture,5,1500,West
2024-11-03,Laptop,Electronics,4,3600,North
2024-11-03,Mouse,Electronics,15,300,East
2024-11-04,Chair,Furniture,12,2400,South
2024-11-04,Monitor,Electronics,6,1800,West
2024-11-04,Laptop,Electronics,2,1800,East'''

echo(sales_csv, "/app/sales/transactions.csv")

# Load data
json_str = csv_to_json("/app/sales/transactions.csv")
sales = json.loads(json_str)

# Convert numeric fields
for sale in sales:
    sale['quantity'] = int(sale['quantity'])
    sale['revenue'] = int(sale['revenue'])

print("=== SALES DATA ANALYSIS ===\\n")
print(f"Total transactions: {len(sales)}\\n")

# Group by category
print("1. SALES BY CATEGORY\\n")
by_category = group_by(sales, lambda s: s['category'])

for category, items in sorted(by_category.items()):
    total_qty = sum(item['quantity'] for item in items)
    total_rev = sum(item['revenue'] for item in items)
    print(f"  {category:15s}: {len(items):2d} transactions, {total_qty:3d} units, ${total_rev:,}")

# Group by region
print("\\n2. SALES BY REGION\\n")
by_region = group_by(sales, lambda s: s['region'])

for region, items in sorted(by_region.items()):
    total_rev = sum(item['revenue'] for item in items)
    avg_rev = total_rev / len(items)
    print(f"  {region:8s}: {len(items):2d} transactions, ${total_rev:,} total, ${avg_rev:,.0f} avg")

# Filter high-value transactions (>= $2000)
print("\\n3. HIGH-VALUE TRANSACTIONS (>= $2000)\\n")
high_value = filter_by(sales, lambda s: s['revenue'] >= 2000)
high_value_sorted = sort_by(high_value, lambda s: s['revenue'], reverse=True)

for sale in high_value_sorted:
    print(f"  {sale['date']:12s} {sale['product']:10s} {sale['region']:8s} ${sale['revenue']:,}")

# Top products by revenue
print("\\n4. TOP PRODUCTS BY TOTAL REVENUE\\n")
by_product = group_by(sales, lambda s: s['product'])
product_revenue = []

for product, items in by_product.items():
    total_rev = sum(item['revenue'] for item in items)
    total_qty = sum(item['quantity'] for item in items)
    product_revenue.append({
        'product': product,
        'revenue': total_rev,
        'quantity': total_qty,
        'transactions': len(items)
    })

top_products = sort_by(product_revenue, lambda p: p['revenue'], reverse=True)

for p in top_products:
    print(f"  {p['product']:10s}: ${p['revenue']:,} ({p['quantity']} units, {p['transactions']} transactions)")

# Daily totals
print("\\n5. DAILY REVENUE TREND\\n")
by_date = group_by(sales, lambda s: s['date'])

for date in sorted(by_date.keys()):
    items = by_date[date]
    daily_rev = sum(item['revenue'] for item in items)
    daily_qty = sum(item['quantity'] for item in items)
    print(f"  {date}: ${daily_rev:,} ({daily_qty} units)")

# Summary statistics
total_revenue = sum(s['revenue'] for s in sales)
total_quantity = sum(s['quantity'] for s in sales)
avg_transaction = total_revenue / len(sales)

print("\\n6. SUMMARY STATISTICS\\n")
print(f"  Total Revenue:      ${total_revenue:,}")
print(f"  Total Units Sold:   {total_quantity}")
print(f"  Avg Transaction:    ${avg_transaction:,.2f}")
print(f"  Unique Products:    {len(by_product)}")
print(f"  Active Regions:     {len(by_region)}")
"""

    sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
    result = sandbox.execute(code)

    print(result.stdout)
    print(f"\n[Fuel consumed: {result.fuel_consumed:,} instructions]")


def demo_report_generation():
    """Example: Generate formatted reports using tabulate."""
    print("\n" + "=" * 60)
    print("DEMO: Report Generation with Tabulate")
    print("=" * 60)

    code = """
from sandbox_utils import csv_to_json, group_by, sort_by, echo, mkdir
import json
import sys
sys.path.insert(0, '/app/site-packages')

from tabulate import tabulate

# Create performance data
mkdir("/app/reports", parents=True)

metrics_csv = '''team,month,tasks_completed,bugs_fixed,code_reviews,on_time_delivery
Alpha,Jan,45,12,38,0.92
Alpha,Feb,52,15,42,0.95
Alpha,Mar,48,10,40,0.89
Beta,Jan,38,8,30,0.85
Beta,Feb,41,11,35,0.88
Beta,Mar,50,14,45,0.93
Gamma,Jan,55,18,50,0.96
Gamma,Feb,58,20,52,0.98
Gamma,Mar,60,22,55,0.97'''

echo(metrics_csv, "/app/reports/metrics.csv")

# Load and process data
json_str = csv_to_json("/app/reports/metrics.csv")
metrics = json.loads(json_str)

# Convert numeric fields
for m in metrics:
    m['tasks_completed'] = int(m['tasks_completed'])
    m['bugs_fixed'] = int(m['bugs_fixed'])
    m['code_reviews'] = int(m['code_reviews'])
    m['on_time_delivery'] = float(m['on_time_delivery'])

print("=== TEAM PERFORMANCE REPORT ===\\n")

# Report 1: Monthly performance by team
print("1. MONTHLY PERFORMANCE BY TEAM\\n")
table_data = []
for m in metrics:
    table_data.append([
        m['team'],
        m['month'],
        m['tasks_completed'],
        m['bugs_fixed'],
        m['code_reviews'],
        f"{m['on_time_delivery']:.0%}"
    ])

headers = ['Team', 'Month', 'Tasks', 'Bugs Fixed', 'Reviews', 'On-Time %']
print(tabulate(table_data, headers=headers, tablefmt='grid'))

# Report 2: Team quarterly summary
print("\\n2. QUARTERLY SUMMARY BY TEAM\\n")
by_team = group_by(metrics, lambda m: m['team'])
summary_data = []

for team in sorted(by_team.keys()):
    team_metrics = by_team[team]
    total_tasks = sum(m['tasks_completed'] for m in team_metrics)
    total_bugs = sum(m['bugs_fixed'] for m in team_metrics)
    total_reviews = sum(m['code_reviews'] for m in team_metrics)
    avg_on_time = sum(m['on_time_delivery'] for m in team_metrics) / len(team_metrics)

    summary_data.append([
        team,
        total_tasks,
        total_bugs,
        total_reviews,
        f"{avg_on_time:.1%}"
    ])

headers = ['Team', 'Total Tasks', 'Total Bugs Fixed', 'Total Reviews', 'Avg On-Time']
print(tabulate(summary_data, headers=headers, tablefmt='fancy_grid'))

# Report 3: Top performers
print("\\n3. TOP PERFORMING MONTHS\\n")
top_performers = sort_by(metrics, lambda m: m['tasks_completed'], reverse=True)[:5]
top_data = []

for m in top_performers:
    top_data.append([
        f"{m['team']} - {m['month']}",
        m['tasks_completed'],
        m['bugs_fixed'],
        f"{m['on_time_delivery']:.0%}"
    ])

headers = ['Team/Month', 'Tasks', 'Bugs', 'On-Time']
print(tabulate(top_data, headers=headers, tablefmt='rounded_grid'))

# Report 4: Monthly trends
print("\\n4. MONTHLY TRENDS (Aggregate)\\n")
by_month = group_by(metrics, lambda m: m['month'])
trend_data = []

for month in ['Jan', 'Feb', 'Mar']:
    month_metrics = by_month[month]
    avg_tasks = sum(m['tasks_completed'] for m in month_metrics) / len(month_metrics)
    avg_bugs = sum(m['bugs_fixed'] for m in month_metrics) / len(month_metrics)
    avg_on_time = sum(m['on_time_delivery'] for m in month_metrics) / len(month_metrics)

    trend_data.append([
        month,
        f"{avg_tasks:.1f}",
        f"{avg_bugs:.1f}",
        f"{avg_on_time:.1%}"
    ])

headers = ['Month', 'Avg Tasks', 'Avg Bugs Fixed', 'Avg On-Time']
print(tabulate(trend_data, headers=headers, tablefmt='simple'))

# Save report to file
report_text = f'''TEAM PERFORMANCE REPORT
{'=' * 60}

QUARTERLY SUMMARY
{tabulate(summary_data, headers=['Team', 'Total Tasks', 'Total Bugs Fixed', 'Total Reviews', 'Avg On-Time'], tablefmt='grid')}

Generated: 2024-11-23
'''

echo(report_text, "/app/reports/summary.txt")
print("\\n✓ Report saved to /app/reports/summary.txt")
"""

    sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
    result = sandbox.execute(code)

    print(result.stdout)
    print(f"\n[Fuel consumed: {result.fuel_consumed:,} instructions]")


def demo_multi_format_processing():
    """Example: Process data in multiple formats (CSV, JSON, YAML)."""
    print("\n" + "=" * 60)
    print("DEMO: Multi-Format Data Processing")
    print("=" * 60)

    code = """
from sandbox_utils import (
    csv_to_json, json_to_csv, echo, cat, mkdir, chunk, unique
)
import json

# Create multi-format configuration
mkdir("/app/config", parents=True)

# CSV format: Environment configuration
env_csv = '''key,value,environment
API_URL,https://api.example.com,production
API_URL,http://localhost:8080,development
DEBUG,false,production
DEBUG,true,development
MAX_CONNECTIONS,100,production
MAX_CONNECTIONS,10,development
TIMEOUT,30,production
TIMEOUT,5,development'''

echo(env_csv, "/app/config/env.csv")

# JSON format: Feature flags
features_json = json.dumps([
    {"name": "new_ui", "enabled": True, "rollout": 100},
    {"name": "api_v2", "enabled": True, "rollout": 50},
    {"name": "experimental", "enabled": False, "rollout": 0},
    {"name": "dark_mode", "enabled": True, "rollout": 100}
], indent=2)

echo(features_json, "/app/config/features.json")

print("=== MULTI-FORMAT CONFIGURATION PROCESSING ===\\n")

# Process CSV configuration
print("1. ENVIRONMENT CONFIGURATION (from CSV)\\n")
env_json = csv_to_json("/app/config/env.csv")
env_config = json.loads(env_json)

# Group by environment
from collections import defaultdict
by_env = defaultdict(dict)

for item in env_config:
    env = item['environment']
    key = item['key']
    value = item['value']
    by_env[env][key] = value

for env in sorted(by_env.keys()):
    print(f"  {env.upper()}:")
    for key, value in sorted(by_env[env].items()):
        print(f"    {key:20s} = {value}")
    print()

# Process JSON features
print("2. FEATURE FLAGS (from JSON)\\n")
with open("/app/config/features.json", 'r') as f:
    features = json.load(f)

enabled_features = [f for f in features if f['enabled']]
print(f"Enabled features: {len(enabled_features)}/{len(features)}\\n")

for feature in features:
    status = "✓ ON " if feature['enabled'] else "✗ OFF"
    print(f"  {status} {feature['name']:20s} (rollout: {feature['rollout']:3d}%)")

# Generate unified configuration file
print("\\n3. UNIFIED CONFIGURATION\\n")

unified = {
    "environments": dict(by_env),
    "features": {f['name']: {"enabled": f['enabled'], "rollout": f['rollout']} for f in features}
}

echo(json.dumps(unified, indent=2), "/app/config/unified.json")
print("✓ Generated unified.json")
print("\\nPreview:")
print(json.dumps(unified, indent=2))

# Generate environment-specific configs
print("\\n4. ENVIRONMENT-SPECIFIC EXPORTS\\n")

for env in ['development', 'production']:
    env_specific = {
        "environment": env,
        "settings": by_env[env],
        "enabled_features": [f['name'] for f in enabled_features]
    }

    filename = f"/app/config/{env}.json"
    echo(json.dumps(env_specific, indent=2), filename)
    print(f"✓ Generated {env}.json")

# List all generated files
print("\\n5. GENERATED CONFIGURATION FILES\\n")
import os
config_files = sorted(os.listdir("/app/config"))

for file in config_files:
    size = os.path.getsize(f"/app/config/{file}")
    print(f"  📄 {file:20s} ({size:4d} bytes)")
"""

    sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
    result = sandbox.execute(code)

    print(result.stdout)
    print(f"\n[Fuel consumed: {result.fuel_consumed:,} instructions]")


def main():
    """Run all data transformation examples."""
    print("\n" + "=" * 60)
    print("DATA TRANSFORMATION EXAMPLES")
    print("Demonstrating sandbox_utils data processing utilities")
    print("=" * 60)

    demo_csv_json_conversion()
    demo_data_aggregation()
    demo_report_generation()
    demo_multi_format_processing()

    print("\n" + "=" * 60)
    print("✓ All data transformation examples completed")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
