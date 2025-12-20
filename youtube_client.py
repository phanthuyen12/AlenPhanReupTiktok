from googleapiclient.discovery import build

def get_latest_video(channel_id: str, api_key: str):
    yt = build(
        "youtube",
        "v3",
        developerKey=api_key,
        cache_discovery=False
    )

    res = yt.search().list(
        part="snippet",
        channelId=channel_id,
        order="date",
        maxResults=1
    ).execute()

    items = res.get("items", [])
    if not items:
        return None

    item = items[0]
    return {
        "video_id": item["id"].get("videoId"),
        "title": item["snippet"]["title"]
    }
