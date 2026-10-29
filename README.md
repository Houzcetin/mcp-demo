# GitHub Maintainer MCP Server

Salt okunur bir MCP sunucusu. Bir açık kaynak projenin bakımcısının sabah rutinini
(issue/PR taraması, bayat kayıtları bulma, sağlık özeti) Claude'a devreder.

## Araçlar

| Araç | Ne yapar |
|---|---|
| `list_open_issues(repo, limit)` | Açık issue'ları listeler (PR'lar hariç) |
| `get_pull_request_summary(repo, number)` | PR'ın durumunu, boyutunu ve değişen dosyalarını özetler |
| `find_stale_items(repo, days)` | N+ gündür hareketsiz issue ve PR'ları bulur |
| `repo_health_report(repo, stale_days)` | Yukarıdakileri birleştirip kısa sağlık raporu çıkarır |

## Kurulum

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Token (önerilir)

GitHub > Settings > Developer settings > Personal access tokens > Fine-grained tokens.
Yalnızca **okuma** izinleri verin (Issues: read, Pull requests: read, Metadata: read).
Token'ı koda veya repoya yazmayın; aşağıdaki Claude Desktop ayarında ortam değişkeni olarak verilir.
Token olmadan da herkese açık repolarda çalışır ama saatte 60 istekle sınırlıdır.

## Claude Desktop'a ekleme

`claude_desktop_config.json` dosyasına ekleyin (Claude Desktop > Settings > Developer > Edit Config):

```json
{
  "mcpServers": {
    "github-maintainer": {
      "command": "/TAM/YOL/.venv/bin/python",
      "args": ["/TAM/YOL/github_mcp_server.py"],
      "env": { "GITHUB_TOKEN": "github_pat_xxx" }
    }
  }
}
```

Windows'ta yollar `C:\\...\\.venv\\Scripts\\python.exe` biçiminde olur. Kaydedip Claude Desktop'ı tamamen kapatıp açın.

## Test

MCP Inspector ile istemciye bağlamadan deneyebilirsiniz:

```bash
mcp dev github_mcp_server.py
```

Claude'da örnek istekler:

- "python/cpython reposunun sağlık raporunu çıkar."
- "owner/repo içinde 60 günden uzun süredir hareketsiz olanları bul ve hangilerini kapatmayı önerirsin?"
- "owner/repo PR #123'ü özetle."

## Demo senaryosu (Zoom kaydı için)

1. Problem: bakımcı her sabah onlarca issue ve PR'ı elle tarıyor.
2. Sunucunun mimarisi: istemci (Claude) - MCP - GitHub REST API.
3. Canlı: sağlık raporu, ardından bayat kayıtlar, ardından tek bir PR özeti.
4. Sınırlar: salt okunur, en fazla 500 açık kayıt taranır, büyük repolarda sayılar alt sınırdır.
