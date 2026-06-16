#!/usr/bin/env python3
"""
pop_topic.py — Read the topic queue and print the next pending topic as JSON.
Marks it as "generating" so concurrent runs don't double-pick.
Called by the cron job before the agent starts writing.
"""
import json, sys, os
from datetime import datetime

QUEUE = os.path.expanduser("~/Desktop/learning/2026/blogs/.queue/topics.json")

def main():
    with open(QUEUE, "r") as f:
        data = json.load(f)

    for topic in data["topics"]:
        if topic["status"] == "pending":
            topic["status"] = "generating"
            topic["generation_started"] = datetime.now().isoformat()
            with open(QUEUE, "w") as f:
                json.dump(data, f, indent=2)
            # Print the topic for the agent to consume
            print(json.dumps(topic, indent=2))
            return

    print("QUEUE_EMPTY")
    sys.exit(0)

if __name__ == "__main__":
    main()
