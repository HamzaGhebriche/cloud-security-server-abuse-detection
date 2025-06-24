# detect_abuse.py

import boto3
import re
import datetime
from collections import Counter

# Constants
LOG_GROUP = "/var/log/auth.log"
REGION = "us-east-1"
THRESHOLD = 5  # Failed attempts before blocking
WHITELIST = ["127.0.0.1"]

def get_failed_ssh_logins():
    """Fetch failed SSH logins from CloudWatch logs."""
    client = boto3.client('logs', region_name=REGION)

    now = int(datetime.datetime.utcnow().timestamp() * 1000)
    start_time = now - (5 * 60 * 1000)  # Last 5 minutes

    try:
        response = client.filter_log_events(
            logGroupName=LOG_GROUP,
            startTime=start_time,
            filterPattern='"Failed password"'
        )
    except Exception as e:
        print(f"Error querying logs: {e}")
        return []

    ip_list = []
    for event in response.get("events", []):
        message = event.get("message", "")
        match = re.search(r'from (\d+\.\d+\.\d+\.\d+)', message)
        if match:
            ip = match.group(1)
            if ip not in WHITELIST:
                ip_list.append(ip)

    return ip_list

def block_ip(ip):
    """Block an IP using security group rules."""
    ec2 = boto3.client("ec2", region_name=REGION)

    try:
        # Find the security group by name or tag
        security_groups = ec2.describe_security_groups(
            Filters=[{'Name': 'group-name', 'Values': ['your-sg-name']}]
        )
        group_id = security_groups['SecurityGroups'][0]['GroupId']

        ec2.revoke_security_group_ingress(
            GroupId=group_id,
            IpProtocol='tcp',
            CidrIp=f"{ip}/32",
            FromPort=22,
            ToPort=22
        )
        print(f"Blocked IP: {ip}")
    except Exception as e:
        print(f"Failed to block IP {ip}: {e}")

def main():
    failed_ips = get_failed_ssh_logins()
    ip_counter = Counter(failed_ips)

    for ip, count in ip_counter.items():
        if count >= THRESHOLD:
            print(f"Suspicious IP {ip} with {count} failed attempts")
            block_ip(ip)

if __name__ == "__main__":
    main()
