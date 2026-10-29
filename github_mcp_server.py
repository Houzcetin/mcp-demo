"""GitHub Maintainer MCP Server (salt okunur).

Araçlar:
  1. list_open_issues
  2. get_pull_request_summary
  3. find_stale_items
  4. repo_health_report

Token: GITHUB_TOKEN ortam değişkeni (salt okunur izin yeterli).
Token olmadan da çalışır ama herkese açık repolarda saatte 60 istekle sınırlıdır.
"""

import os
import re
from datetime import datetime, timedelta, timezone

import httpx

try:  # mcp 2.x: FastMCP, MCPServer olarak yeniden adlandırıldı
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP

mcp = FastMCP("github-maintainer")

API = "https://api.github.com"
MAX_PAGES = 5  # sayfa başına 100 kayıt -> en fazla 500 kayıt taranır


# ---------------------------------------------------------------- yardımcılar
def _headers() -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "github-maintainer-mcp",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _check_repo(repo: str) -> str:
    repo = repo.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Repo 'sahip/isim' biçiminde olmalı, örn: 'python/cpython'.")
    return repo


async def _get(path: str, params: dict | None = None):
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{API}{path}", headers=_headers(), params=params)
    if resp.status_code == 404:
        raise ValueError("Bulunamadı (404). Repo adını kontrol edin; özel repo ise token izni gerekir.")
    if resp.status_code in (401, 403):
        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining == "0":
            raise ValueError("GitHub istek limiti doldu. GITHUB_TOKEN tanımlayın veya biraz bekleyin.")
        raise ValueError(f"Erişim reddedildi ({resp.status_code}). Token'ı ve izinlerini kontrol edin.")
    resp.raise_for_status()
    return resp.json()


async def _fetch_open_items(repo: str) -> list[dict]:
    """Açık issue ve PR'ları (GitHub ikisini aynı uçta döndürür) en eski güncellemeden başlayarak çeker."""
    items: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        batch = await _get(
            f"/repos/{repo}/issues",
            {"state": "open", "sort": "updated", "direction": "asc", "per_page": 100, "page": page},
        )
        items.extend(batch)
        if len(batch) < 100:
            break
    return items


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _age_days(value: str) -> int:
    return (datetime.now(timezone.utc) - _parse_time(value)).days


def _labels(item: dict) -> str:
    names = [label["name"] for label in item.get("labels", [])]
    return f" [{', '.join(names)}]" if names else ""


# -------------------------------------------------------------------- araçlar
@mcp.tool()
async def list_open_issues(repo: str, limit: int = 20) -> str:
    """Bir repodaki açık issue'ları (PR'lar hariç) en son güncellenenden başlayarak listeler.

    Args:
        repo: 'sahip/isim' biçiminde repo, örn. 'python/cpython'.
        limit: Döndürülecek en fazla issue sayısı (1-50).
    """
    repo = _check_repo(repo)
    limit = max(1, min(limit, 50))
    data = await _get(
        f"/repos/{repo}/issues",
        {"state": "open", "sort": "updated", "direction": "desc", "per_page": 100},
    )
    issues = [i for i in data if "pull_request" not in i][:limit]
    if not issues:
        return f"{repo} reposunda açık issue bulunamadı."

    lines = [f"## {repo} - açık issue'lar ({len(issues)} adet gösteriliyor)"]
    for i in issues:
        lines.append(
            f"- #{i['number']} {i['title']}{_labels(i)} "
            f"(@{i['user']['login']}, {i['comments']} yorum, {_age_days(i['updated_at'])} gün önce güncellendi)"
        )
    return "\n".join(lines)


@mcp.tool()
async def get_pull_request_summary(repo: str, number: int) -> str:
    """Bir pull request'in durumunu ve değişikliklerini özetler.

    Args:
        repo: 'sahip/isim' biçiminde repo.
        number: Pull request numarası.
    """
    repo = _check_repo(repo)
    pr = await _get(f"/repos/{repo}/pulls/{number}")
    files = await _get(f"/repos/{repo}/pulls/{number}/files", {"per_page": 100})

    if pr.get("merged"):
        state = "birleştirildi"
    elif pr["state"] == "closed":
        state = "kapatıldı"
    else:
        state = "taslak" if pr.get("draft") else "açık"

    body = (pr.get("body") or "").strip()
    if len(body) > 600:
        body = body[:600] + "..."

    lines = [
        f"## PR #{number}: {pr['title']}",
        f"- Durum: {state}",
        f"- Yazar: @{pr['user']['login']}",
        f"- Dallar: {pr['head']['ref']} -> {pr['base']['ref']}",
        f"- Boyut: +{pr['additions']} / -{pr['deletions']} satır, {pr['changed_files']} dosya, {pr['commits']} commit",
        f"- Yorum: {pr['comments']} genel, {pr['review_comments']} kod yorumu",
        f"- Oluşturulma: {_age_days(pr['created_at'])} gün önce, son güncelleme: {_age_days(pr['updated_at'])} gün önce",
    ]
    if body:
        lines += ["", "### Açıklama", body]

    lines += ["", "### En çok değişen dosyalar"]
    top = sorted(files, key=lambda f: f["changes"], reverse=True)[:10]
    for f in top:
        lines.append(f"- {f['filename']} ({f['status']}, +{f['additions']} / -{f['deletions']})")
    if pr["changed_files"] > len(files):
        lines.append(f"- ... toplam {pr['changed_files']} dosya (ilk {len(files)} tanesi analiz edildi)")
    return "\n".join(lines)


@mcp.tool()
async def find_stale_items(repo: str, days: int = 30) -> str:
    """Belirli bir süredir hareketsiz kalan açık issue ve PR'ları bulur.

    Args:
        repo: 'sahip/isim' biçiminde repo.
        days: Kaç gündür güncellenmemiş olanlar bayat sayılsın (varsayılan 30).
    """
    repo = _check_repo(repo)
    days = max(1, days)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    items = await _fetch_open_items(repo)
    stale = [i for i in items if _parse_time(i["updated_at"]) < cutoff]
    if not stale:
        return f"{repo} reposunda {days} günden uzun süredir hareketsiz açık kayıt yok."

    issues = [i for i in stale if "pull_request" not in i]
    prs = [i for i in stale if "pull_request" in i]

    lines = [f"## {repo} - {days}+ gündür hareketsiz: {len(issues)} issue, {len(prs)} PR"]
    for title, group in (("Issue'lar", issues), ("Pull request'ler", prs)):
        if not group:
            continue
        lines.append(f"\n### {title} (en eskiden başlayarak, en fazla 15)")
        for i in group[:15]:
            lines.append(f"- #{i['number']} {i['title']}{_labels(i)} - {_age_days(i['updated_at'])} gündür sessiz")
    if len(items) >= MAX_PAGES * 100:
        lines.append(f"\nNot: yalnızca en eski güncellenen {MAX_PAGES * 100} açık kayıt tarandı.")
    return "\n".join(lines)


@mcp.tool()
async def repo_health_report(repo: str, stale_days: int = 30) -> str:
    """Repo için kısa bir sağlık raporu üretir (açık iş yükü, bayat kayıtlar, sahipsiz issue'lar).

    Args:
        repo: 'sahip/isim' biçiminde repo.
        stale_days: Bayatlık eşiği, gün cinsinden (varsayılan 30).
    """
    repo = _check_repo(repo)
    cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)

    info = await _get(f"/repos/{repo}")
    items = await _fetch_open_items(repo)

    issues = [i for i in items if "pull_request" not in i]
    prs = [i for i in items if "pull_request" in i]
    stale_issues = [i for i in issues if _parse_time(i["updated_at"]) < cutoff]
    stale_prs = [i for i in prs if _parse_time(i["updated_at"]) < cutoff]
    unassigned = [i for i in issues if not i.get("assignees")]
    no_label = [i for i in issues if not i.get("labels")]
    no_comment = [i for i in issues if i.get("comments", 0) == 0]
    oldest_pr = max(prs, key=lambda i: _age_days(i["created_at"]), default=None)

    def pct(part: int, total: int) -> str:
        return f"%{round(100 * part / total)}" if total else "-"

    # Basit, açıklanabilir bir durum yorumu
    problems = []
    if issues and len(stale_issues) / len(issues) > 0.5:
        problems.append("issue'ların yarısından fazlası bayat")
    if prs and len(stale_prs) / len(prs) > 0.5:
        problems.append("PR'ların yarısından fazlası bayat")
    if issues and len(unassigned) / len(issues) > 0.8:
        problems.append("çoğu issue'nun sorumlusu yok")
    verdict = "Dikkat gerekiyor: " + "; ".join(problems) if problems else "Genel durum sağlıklı görünüyor."

    lines = [
        f"## Sağlık raporu: {repo}",
        f"- Yıldız: {info['stargazers_count']}, fork: {info['forks_count']}, "
        f"son push: {_age_days(info['pushed_at'])} gün önce",
        f"- Açık issue: {len(issues)}, açık PR: {len(prs)}",
        f"- Bayat issue ({stale_days}+ gün): {len(stale_issues)} ({pct(len(stale_issues), len(issues))})",
        f"- Bayat PR ({stale_days}+ gün): {len(stale_prs)} ({pct(len(stale_prs), len(prs))})",
        f"- Sorumlusu olmayan issue: {len(unassigned)} ({pct(len(unassigned), len(issues))})",
        f"- Etiketsiz issue: {len(no_label)} ({pct(len(no_label), len(issues))})",
        f"- Hiç yorum almamış issue: {len(no_comment)} ({pct(len(no_comment), len(issues))})",
    ]
    if oldest_pr:
        lines.append(f"- En eski açık PR: #{oldest_pr['number']} {oldest_pr['title']} ({_age_days(oldest_pr['created_at'])} gündür açık)")
    lines += ["", f"**Değerlendirme:** {verdict}"]
    if len(items) >= MAX_PAGES * 100:
        lines.append(f"\nNot: büyük repo, yalnızca en eski güncellenen {MAX_PAGES * 100} açık kayıt tarandı; sayılar alt sınırdır.")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
