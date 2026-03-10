import os
import re
import requests
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from bs4 import BeautifulSoup

DOWNLOAD_FOLDER = "downloads"
LINKS_FILE = "links.txt"
MAX_WORKERS = 20

HEADERS = {"User-Agent": "Mozilla/5.0"}

session = requests.Session()
session.headers.update(HEADERS)


def get_folder_key(url):
    match = re.search(r"/folder/([^/]+)", url)
    if match:
        return match.group(1)
    return None


def get_direct_link(url):
    try:
        res = session.get(url, timeout=20)

        soup = BeautifulSoup(res.text, "html.parser")

        btn = soup.find("a", {"id": "downloadButton"})
        if btn:
            return btn.get("href")

        pattern = r'https?://download[0-9]+\.mediafire\.com/[^"\']+'
        links = re.findall(pattern, res.text)

        if links:
            return links[0]

    except Exception:
        pass

    return None


def download_file(url, folder_path=""):
    direct_link = get_direct_link(url)

    if not direct_link:
        print("No se pudo sacar link directo:", url)
        return

    try:
        r = session.get(direct_link, stream=True)

        cd = r.headers.get("content-disposition")

        if cd:
            name = re.findall('filename="(.+)"', cd)
            filename = name[0] if name else direct_link.split("/")[-1]
        else:
            filename = direct_link.split("/")[-1]

        save_folder = os.path.join(DOWNLOAD_FOLDER, folder_path)
        os.makedirs(save_folder, exist_ok=True)

        file_path = os.path.join(save_folder, filename)

        total_size = int(r.headers.get("content-length", 0))

        with open(file_path, "wb") as f, tqdm(
            desc=filename, total=total_size, unit="B", unit_scale=True, leave=False
        ) as bar:

            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)
                    bar.update(len(chunk))

        print("Descargado:", filename)

    except Exception as e:
        print("Error descargando:", e)


def list_folder(folder_key, current_path=""):

    api_url = "https://www.mediafire.com/api/1.5/folder/get_content.php"

    params = {
        "folder_key": folder_key,
        "content_type": "files",
        "response_format": "json",
    }

    r = session.get(api_url, params=params)
    data = r.json()

    folder_content = data.get("response", {}).get("folder_content", {})

    files_to_download = []

    for f in folder_content.get("files", []):
        files_to_download.append((f["links"]["normal_download"], current_path))

    params["content_type"] = "folders"

    r = session.get(api_url, params=params)
    data = r.json()

    folder_content = data.get("response", {}).get("folder_content", {})

    for folder in folder_content.get("folders", []):
        name = folder["name"]
        key = folder["folderkey"]

        new_path = os.path.join(current_path, name)

        print("Entrando a carpeta:", new_path)

        files_to_download.extend(list_folder(key, new_path))

    return files_to_download


def process_folder(url):
    folder_key = get_folder_key(url)

    print("Escaneando folder...")

    files = list_folder(folder_key)

    print("Archivos encontrados:", len(files))

    with ThreadPoolExecutor(MAX_WORKERS) as pool:
        for file_url, path in files:
            pool.submit(download_file, file_url, path)


def process_file(url):
    download_file(url)


def main():
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

    if not os.path.exists(LINKS_FILE):
        with open(LINKS_FILE, "w") as f:
            f.write("# pega tus links aca\n")

        print("Se creó links.txt")
        return

    with open(LINKS_FILE) as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    for url in urls:

        if "/folder/" in url:
            process_folder(url)
        else:
            process_file(url)

    print("\nListo, todas las descargas terminaron")


if __name__ == "__main__":
    main()
