import configparser
import requests
from pathlib import Path
import xml.etree.ElementTree as ET
from datetime import datetime
import os

def load_credentials():
    config = configparser.ConfigParser()
    config.read('config.ini')

    nextcloud_url = config.get('nextcloud', 'NEXTCLOUD_URL')
    username = config.get('nextcloud', 'NEXTCLOUD_USER')
    password = config.get('nextcloud', 'NEXTCLOUD_PASS')

    return username, password, nextcloud_url

def upload_to_nextcloud(local_file_path: str, remote_file_path: str):
    # ユーザー名、パスワード、NextcloudのURLを設定
    (username, password, nextcloud_url) = load_credentials()

    # WebDAVエンドポイント
    webdav_url = f'{nextcloud_url}/remote.php/dav/files/{username}'

    # フォルダが存在するかどうかを確認
    folder_url = os.path.dirname(remote_file_path)
    folder_exists_url = f'{webdav_url}{folder_url}'
    folder_exists_response = requests.request('PROPFIND', folder_exists_url, auth=(username, password))

    # フォルダが存在しない場合、フォルダを作成
    if folder_exists_response.status_code == 404:
        create_folder_response = requests.request('MKCOL', folder_exists_url, auth=(username, password))
        if create_folder_response.status_code != 201:
            error_message = f'Failed to create folder with status code: {create_folder_response.status_code}'
            print(error_message)
            return False, error_message
    
    # ファイルをアップロード
    upload_url = f'{webdav_url}{remote_file_path}'
    with open(local_file_path, 'rb') as f:
        upload_response = requests.put(upload_url, data=f, auth=(username, password))
        if upload_response.status_code != 201:
            error_message = f'Failed to upload file with status code: {upload_response.status_code}'
            print(error_message)
            return False, error_message
    
    return True, None

def create_public_link(remote_file_path: str):
    # ユーザー名、パスワード、NextcloudのURLを設定
    (username, password, nextcloud_url) = load_credentials()

    # OCS APIエンドポイントを設定
    ocs_url = f'{nextcloud_url}/ocs/v2.php/apps/files_sharing/api/v1/shares'

    # パラメータを設定
    params = {
        'path': remote_file_path,
        'shareType': 3,  # 3 はパブリックリンクの共有タイプ
        'permissions': 1  # 1 は閲覧のみの権限
    }

    # 必要なヘッダーを追加
    headers = {'OCS-APIRequest': 'true'}

    # 公開リンクを作成
    response = requests.post(ocs_url, params=params, auth=(username, password), headers=headers)

    #print(f'Response status code: {response.status_code}')
    #print(f'Response text: {response.text}')

    if response.status_code == 200:
        try:
            root = ET.fromstring(response.text)
            public_link = root.find('.//url').text
            direct_link = f'{public_link}/download'  # 直リンクURLを作成
            print(f'Direct link created: {direct_link}')
            return direct_link, None
        except ET.ParseError as e:
            error_message = f'Failed to parse XML: {e}'
            print(error_message)
            return None, error_message
    else:
        error_message = f'Failed to create public link with status code: {response.status_code}'
        print(error_message)
        return None, error_message
        
def test_upload_to_nextcloud():
    local_file_path = './test.txt'
    remote_folder_path = '/testDir'
    remote_file_path = f'{remote_folder_path}/{Path(local_file_path).name}'
    
    upload_result = upload_to_nextcloud(local_file_path, remote_file_path)
    assert upload_result, 'File upload failed'

    direct_link = create_public_link(remote_file_path)
    assert direct_link, 'Failed to create direct link'


if __name__ == '__main__':
    test_upload_to_nextcloud()
