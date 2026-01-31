import os
import re
from pathlib import Path
from getpass import getpass
from playwright.sync_api import sync_playwright, Page
from urllib.parse import urlparse

from components.utils import full_url, safe_filename , suggest_filename


class Scraper:
    def __init__(self, cfg):
        self.cfg = cfg
        self.allow = re.compile(cfg.allow_path_regex)


    def _is_login_page(self, page: Page) -> bool:
        return self.cfg.login_path in page.url


    def _login(self, page: Page) -> None:
        user = input("Username: ").strip()
        pw = getpass("Password: ")

        page.goto(full_url(self.cfg.base, self.cfg.login_path))
        page.fill(self.cfg.sel_user, user)
        page.fill(self.cfg.sel_pass, pw)
        page.click(self.cfg.sel_submit)
        page.wait_for_load_state("networkidle")


    def ensure_logged_in(self, page: Page) -> None:
        if self._is_login_page(page):
            self._login(page)


    def collect_links(self, page: Page) -> list[str]:
        hrefs = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => e.getAttribute('href')).filter(Boolean)"
        )

        links = []
        for h in hrefs:
            path = h[len(self.cfg.base):] if h.startswith(self.cfg.base) else h
            if self.allow.match(path):
                links.append(full_url(self.cfg.base, h))

        return list(dict.fromkeys(links))  # unique, order-preserving


    def create_page_folder(self, idx: int, url: str, page: Page) -> Path:
        title = page.title() or url
        folder = self.cfg.out_dir / f"{idx:03d}_{safe_filename(title)}"
        folder.mkdir(parents=True, exist_ok=True)
        
        if self.cfg.include_url_txt:
            (folder / "url.txt").write_text(url + "\n", encoding="utf-8")

        return folder


    def save_pdf(self, page: Page, folder: Path) -> None:
        page.pdf(
            path=str(folder / "task.pdf"),
            format=self.cfg.pdf_format,
            print_background=self.cfg.print_background,
        )


    def run(self) -> None:
        self.cfg.out_dir.mkdir(parents=True, exist_ok=True)
        start_url = full_url(self.cfg.base, self.cfg.start_path)

        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=self.cfg.profile_dir,
                headless=self.cfg.headless,
            )
            page = ctx.new_page()

            page.goto(start_url)
            self.ensure_logged_in(page)
            page.goto(start_url, wait_until="networkidle")

            links = self.collect_links(page)
            print(f"Gefunden: {len(links)} Seiten")

            for i, url in enumerate(links, 1):
                print(f"[{i}/{len(links)}] {url}")
                page.goto(url, wait_until="networkidle")
                
                folder = self.create_page_folder(i, url, page)
                
                self.save_pdf(page, folder)

                n = self.save_attachments_for_current_page(page, folder)
                if n:
                    print(f"  ✓ attachments saved: {n}")

            # end
            ctx.close()
 
 
    def _collect_resource_links(self, page) -> list[str]:
        hrefs = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => e.getAttribute('href')).filter(Boolean)"
        )

        out = []

        for h in hrefs:
            url = full_url(self.cfg.base, h)

            # download from allowed hosts only!
            host = urlparse(url).netloc
            if host not in self.cfg.allowed_resource_hosts:
                continue

            u = url.lower()

            # mode=dl
            if self.cfg.include_mode_dl and "mode=dl" in u:
                out.append(url)

            # mode=raw
            if self.cfg.include_mode_raw and "mode=raw" in u:
                out.append(url)

            # archive: zip
            if self.cfg.include_archive_zip and u.endswith(".zip"):
                out.append(url)

            # archive: tgz
            if self.cfg.include_archive_tgz and u.endswith(( ".tgz", ".tar.gz", ".gz")):
                out.append(url)

            # PDFs
            if self.cfg.include_pdfs and u.endswith(".pdf"):
                out.append(url)

            # img
            if self.cfg.include_images and u.endswith((".png", ".jpg", ".jpeg")):
                out.append(url)

        # unique, order-preserving
        return list(dict.fromkeys(out))


    def save_attachments_for_current_page(self, page, page_folder: Path) -> int:
        """
        - erstellt attachments/ in Seitenordner
        - sammelt Links (mode=raw / mode=dl / .zip/.md/...)
        - lädt Inhalte über page.request.get (Session/Cookies inklusive)
        - schreibt Text/Binary in Dateien
        Returns: Anzahl erfolgreich gespeicherter Dateien
        """
        att_dir = page_folder / "attachments"
        att_dir.mkdir(parents=True, exist_ok=True)

        links = self._collect_resource_links(page)
        if not links:
            return 0

        saved = 0

        for url in links:
            try:
                resp = page.request.get(url, timeout=30_000)
                if not resp.ok:
                    print(f"  ⚠ skip (HTTP {resp.status}): {url}")
                    continue
                
                filename = suggest_filename(url, att_dir)
                target = att_dir / filename

                if target.exists():
                    stem, ext = os.path.splitext(filename)
                    k = 2
                    while True:
                        candidate = att_dir / f"{stem}_{k}{ext}"
                        if not candidate.exists():
                            target = candidate
                            break
                        k += 1

                ctype = (resp.headers.get("content-type") or "").lower()

                if "text" in ctype or "json" in ctype or url.lower().endswith((".md", ".txt")) or "mode=raw" in url.lower():
                    target.write_text(resp.text(), encoding="utf-8")
                else:
                    target.write_bytes(resp.body())

                saved += 1
            except Exception as e:
                print(f"  ⚠ failed: {url} ({e})")

        return saved