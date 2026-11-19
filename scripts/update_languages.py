
import os
import json
import base64
import html
import urllib.request
import urllib.error
from collections import defaultdict

USERNAME = os.environ["GH_USERNAME"]
READ_TOKEN = os.environ["GH_STATS_TOKEN"]
WRITE_TOKEN = os.environ["PROFILE_TOKEN"]

PROFILE_REPO = USERNAME
EXCLUDED_REPOS = {"Ismail", PROFILE_REPO}
EXCLUDED_LANGUAGES = {"PHP"}

API = "https://api.github.com"
CARD_PATH = "assets/languages.svg"

LANGUAGE_COLORS = {
    "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a",
    "Python": "#3572A5",
    "Java": "#b07219",
    "C#": "#178600",
    "C++": "#f34b7d",
    "HTML": "#e34c26",
    "CSS": "#663399",
    "Vue": "#41b883",
    "Go": "#00ADD8",
    "Ruby": "#701516",
    "Swift": "#F05138",
    "Kotlin": "#A97BFF",
    "Dart": "#00B4AB",
    "Shell": "#89e051",
    "Rust": "#dea584",
}


def request(url, token, method="GET", data=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "GitHub-Language-Stats"
    }

    body = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method
    )

    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API error {error.code}: {details}"
        ) from error


def upload_file(path, content, message):
    url = (
        f"{API}/repos/{USERNAME}/{PROFILE_REPO}"
        f"/contents/{path}"
    )

    payload = {
        "message": message,
        "content": base64.b64encode(
            content.encode("utf-8")
        ).decode("ascii")
    }

    try:
        existing = request(url, WRITE_TOKEN)
        payload["sha"] = existing["sha"]
    except RuntimeError as error:
        if "404" not in str(error):
            raise

    request(
        url,
        WRITE_TOKEN,
        method="PUT",
        data=payload
    )


# 1. Fetch owned repositories, including private repositories.

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


# 2. Calculate actual language usage.

totals = defaultdict(int)
checked_repositories = 0

for repo in repositories:
    if repo["name"] in EXCLUDED_REPOS:
        continue

    if repo["fork"] or repo["archived"]:
        continue

    languages = request(
        f"{API}/repos/{repo['full_name']}/languages",
        READ_TOKEN
    )

    checked_repositories += 1

    for language, size in languages.items():
        if language in EXCLUDED_LANGUAGES:
            continue

        totals[language] += size


total_bytes = sum(totals.values())

if total_bytes == 0:
    raise RuntimeError(
        "No language data found. Check repository access."
    )


# 3. Generate a GitHub-style SVG language card.

languages = sorted(
    totals.items(),
    key=lambda item: item[1],
    reverse=True
)[:10]

card_width = 600
row_height = 43
card_height = 105 + len(languages) * row_height + 25

svg = [
    f'<svg xmlns="http://www.w3.org/2000/svg" '
    f'width="{card_width}" height="{card_height}" '
    f'viewBox="0 0 {card_width} {card_height}">',
    '<rect width="100%" height="100%" rx="10" '
    'fill="#0d1117" stroke="#30363d"/>',
    '<text x="25" y="38" fill="#e6edf3" '
    'font-family="Arial, sans-serif" font-size="19" '
    'font-weight="600">Most Used Languages</text>',
    '<text x="25" y="62" fill="#8b949e" '
    'font-family="Arial, sans-serif" font-size="11">'
    'Public and private repositories, excluding PHP'
    '</text>'
]

bar_x = 25
bar_y = 78
bar_width = 550
bar_height = 9

# Distribution bar.
svg.append(
    f'<rect x="{bar_x}" y="{bar_y}" '
    f'width="{bar_width}" height="{bar_height}" '
    'rx="5" fill="#30363d"/>'
)

offset = 0

for language, size in languages:
    percentage = size / total_bytes * 100
    segment_width = bar_width * percentage / 100
    color = LANGUAGE_COLORS.get(language, "#8b949e")

    svg.append(
        f'<rect x="{bar_x + offset:.2f}" y="{bar_y}" '
        f'width="{segment_width:.2f}" height="{bar_height}" '
        f'fill="{color}"/>'
    )

    offset += segment_width

# Individual language rows.
for index, (language, size) in enumerate(languages):
    y = 119 + index * row_height
    percentage = size / total_bytes * 100
    color = LANGUAGE_COLORS.get(language, "#8b949e")
    safe_name = html.escape(language)

    svg.extend([
        f'<circle cx="31" cy="{y - 5}" r="5" fill="{color}"/>',
        f'<text x="46" y="{y}" fill="#e6edf3" '
        f'font-family="Arial, sans-serif" font-size="13">'
        f'{safe_name}</text>',
        f'<text x="575" y="{y}" fill="#e6edf3" '
        f'text-anchor="end" font-family="Arial, sans-serif" '
        f'font-size="13" font-weight="600">'
        f'{percentage:.2f}%</text>'
    ])

svg.append('</svg>')

svg_content = "\n".join(svg)


# 4. Upload or update the SVG card in the profile repository.

upload_file(
    CARD_PATH,
    svg_content,
    "Update GitHub language statistics card"
)


# 5. Update the profile README.

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
    raise RuntimeError(
        "Language markers missing in profile README."
    )

before, remaining = readme.split(start, 1)
_, after = remaining.split(end, 1)

new_section = (
    f'{start}\n'
    f'![GitHub Language Statistics]'
    f'(https://raw.githubusercontent.com/'
    f'{USERNAME}/{PROFILE_REPO}/main/{CARD_PATH})\n'
    f'{end}'
)

updated_readme = before + new_section + after

request(
    readme_url,
    WRITE_TOKEN,
    method="PUT",
    data={
        "message": "Update GitHub language statistics card",
        "content": base64.b64encode(
            updated_readme.encode("utf-8")
        ).decode("ascii"),
        "sha": readme_data["sha"]
    }
)

print("Successfully updated GitHub language card!")
print(f"Repositories checked: {checked_repositories}")
print(f"Languages displayed: {len(languages)}")
print("Excluded languages: PHP")
print("Card uploaded: " + CARD_PATH)

for language, size in languages:
    print(
        f"{language}: {size / total_bytes * 100:.2f}%"
    )
