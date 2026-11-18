
import os
import json
import base64
import urllib.request
from collections import defaultdict
from urllib.error import HTTPError

USERNAME = os.environ["GH_USERNAME"]
READ_TOKEN = os.environ["GH_STATS_TOKEN"]
WRITE_TOKEN = os.environ["PROFILE_TOKEN"]

PROFILE_REPO = USERNAME
EXCLUDED_REPOS = {"Ismail", PROFILE_REPO}

API = "https://api.github.com"

def request(url, token, method="GET", data=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    body = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode()

    req = urllib.request.Request(
        url, data=body, headers=headers, method=method
    )

    with urllib.request.urlopen(req) as response:
        return json.loads(response.read())

# 1. Fetch all repositories owned by the account
repositories = []
page = 1

while True:
    url = (
        f"{API}/user/repos"
        f"?visibility=all&affiliation=owner"
        f"&per_page=100&page={page}"
    )

    batch = request(url, READ_TOKEN)

    if not batch:
        break

    repositories.extend(batch)

    if len(batch) < 100:
        break

    page += 1

# 2. Calculate language usage
totals = defaultdict(int)

for repo in repositories:
    if repo["name"] in EXCLUDED_REPOS:
        continue

    if repo["fork"] or repo["archived"]:
        continue

    languages = request(
        f"{API}/repos/{repo['full_name']}/languages",
        READ_TOKEN
    )

    for language, size in languages.items():
        totals[language] += size

total_bytes = sum(totals.values())

if total_bytes == 0:
    raise RuntimeError("No programming language data found.")

# 3. Generate language table
lines = [
    "| Language | Usage |",
    "|---|---:|"
]

for language, size in sorted(
    totals.items(),
    key=lambda item: item[1],
    reverse=True
)[:10]:
    percentage = size / total_bytes * 100
    lines.append(f"| {language} | {percentage:.2f}% |")

new_section = "\n".join(lines)

# 4. Fetch your actual public profile README
readme_url = (
    f"{API}/repos/{USERNAME}/{PROFILE_REPO}"
    "/contents/README.md"
)

readme_data = request(readme_url, WRITE_TOKEN)

readme = base64.b64decode(
    readme_data["content"]
).decode("utf-8")

start = "<!-- LANGUAGES-START -->"
end = "<!-- LANGUAGES-END -->"

if start not in readme or end not in readme:
    raise RuntimeError("Language markers missing in profile README.")

before, remaining = readme.split(start, 1)
_, after = remaining.split(end, 1)

updated_readme = (
    before + start + "\n"
    + new_section + "\n"
    + end + after
)

# 5. Update profile README through GitHub API
request(
    readme_url,
    WRITE_TOKEN,
    method="PUT",
    data={
        "message": "Update private and public language statistics",
        "content": base64.b64encode(
            updated_readme.encode("utf-8")
        ).decode("ascii"),
        "sha": readme_data["sha"]
    }
)

print("Successfully updated GitHub profile!")
print(f"Repositories checked: {len(repositories)}")
print(f"Languages found: {len(totals)}")
