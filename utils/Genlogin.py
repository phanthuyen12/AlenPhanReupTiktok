# file: gpm.py
import requests

class GEN:
    def __init__(self, base_url="http://localhost:55550/backend/profiles"):
        self.base_url = base_url


    def loads_profile(self, offset=0, limit=1000):
        url = self.base_url
        params = {'limit': limit, 'offset': offset}
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json().get('data')
            return {
                'profiles': data.get('items'),
                'pagination': data.get('pagination')
            }
        except requests.exceptions.RequestException as err:
            return err.response.json()
    def stop_profile(self, profile_id):
        """
        Stop profile
        :param profile_id: int or str
        :return: True nếu thành công, False nếu thất bại
        """
        try:
            url = f"{self.base_url}/{profile_id}/stop"
            res = requests.put(url, timeout=10)
            return res.status_code == 200
        except Exception as e:
            print(f"[GPM] Stop error: {e}")
            return False

    def start_profile(self, profile_id):
        """
        Start profile
        :param profile_id: int or str
        :return: dict dữ liệu profile nếu thành công, None nếu thất bại
        """
        try:
            url = f"{self.base_url}/{profile_id}/start"
            res = requests.put(url, timeout=10)
            if res.status_code == 200 and res.json().get("success"):
                return res.json()
            return None
        except Exception as e:
            print(f"[GPM] Start error: {e}")
            return None
