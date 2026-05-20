import requests

url = "http://localhost:8000/add_avis"

test_cases = [
    "khayeb yesser",
    "bahi w nthif",
    "retard ma famech bus",
    "tayara",
    "catastrophe msakh"
]

for t in test_cases:
    payload = {
        "commentaire": t,
        "note": 3,
        "client_id": 1,
        "parcours_id": 1
    }
    response = requests.post(url, json=payload)
    print(f"Comment: {t}")
    print(response.json()['ai_analysis'])
    print("-" * 30)