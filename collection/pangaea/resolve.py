import requests

def resolve_url(url):
    try:
        response = requests.head(url, allow_redirects=True)
        if response.status_code == 303:
            return response.url  # The final URL after following redirects
        else:
            return None  # URL didn't result in a 303 status code
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None

# Example usage
url = "https://doi.org/10.1594/PANGAEA.928381"

final_url = resolve_url(url)

if final_url:
    print(f"The resolved URL is: {final_url}")
else:
    print("Failed to resolve the URL.")

