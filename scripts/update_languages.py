
import json
import os
import urllib.request
from collections import defaultdict

TOKEN = os.environ["GH_STATS_TOKEN"]
USERNAME = os.environ["GH_USERNAME"]

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

def github_api(url):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())

# Get all repositories owned by the account
repositories = []
page = 1

while True:
    url = (
        f"https://api.github.com/user/repos"
        f"?visibility=all&affiliation=owner"
        f"&per_page=100&page={page}"
    )

    batch = github_api(url)

    if not batch:
        break

    repositories.extend(batch)
    page += 1

# Aggregate language bytes across repositories
totals = defaultdict(int)

for repo in repositories:
    if repo["fork"] or repo["archived"]:
        continue

    url = (
        f"https://api.github.com/repos/"
        f"{USERNAME}/{repo['name']}/languages"
    )

    languages = github_api(url)

    for language, size in languages.items():
        totals[language] += size

# Sort by total bytes
sorted_languages = sorted(
    totals.items(),
    key=lambda item: item[1],
    reverse=True
)

total_bytes = sum(totals.values())

if not total_bytes:
    raise RuntimeError("No language statistics found.")

# Generate Markdown
lines = [
    "## Most Used Languages",
    "",
    "| Language | Usage |",
    "|---|---:|"
]

for language, size in sorted_languages[:10]:
    percentage = size / total_bytes * 100
    lines.append(f"| {language} | {percentage:.2f}% |")

new_section = "\n".join(lines)

# Update README between markers
with open("README.md", "r", encoding="utf-8") as file:
    readme = file.read()

start = "<!-- LANGUAGES-START -->"
end = "<!-- LANGUAGES-END -->"

if start not in readme or end not in readme:
    raise RuntimeError("Language markers missing in README.")

before, remainder = readme.split(start, 1)
_, after = remainder.split(end, 1)

updated = (
    before
    + start
    + "\n"
    + new_section
    + "\n"
    + end
    + after
)

with open("README.md", "w", encoding="utf-8") as file:
    file.write(updated)

print("Language statistics updated successfully.")
