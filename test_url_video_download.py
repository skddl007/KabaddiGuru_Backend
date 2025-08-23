import requests

url = "https://vod.cricket-21.com/volume1/Kabaddi%20Videos/4231/TT%20Vs%20BB%2018-10-24_2.MP4"
output_file = "TT_vs_BB_18-10-24.mp4"

# Disable SSL warnings (optional)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Download with SSL verification turned off
with requests.get(url, stream=True, verify=False) as r:
    r.raise_for_status()
    with open(output_file, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

print("Download complete:", output_file)
