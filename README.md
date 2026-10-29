# AI-Drive Analyzer

## User Flow

AI-Drive Analyzer lets users ask questions about files in Google Drive. A new user can use it as follows:

1. **Open the app and connect Google Drive.** On the dashboard, select **Connect Google Drive** and sign in with Google. Review the consent screen and grant the requested read-only Drive access; the app needs permission to see and download Drive files to analyze them. After authorization, the dashboard shows the connected account and loads the Drive catalog.
2. **Browse the Drive catalog.** Use the **All Files**, **Docs**, **Sheets**, and **PDFs** tabs or the search field to find documents. Select one or more files to limit a question to those files. Leave the selection empty if you want the app to find relevant files automatically.
3. **Ask a question.** Enter a question in the chat and send it. The app checks Drive file names (not document contents) for title words that appear in the question. If a title matches, that named file takes priority over other selected files. Questions asking for section, chapter, or worksheet/tab inventories read all indexed chunks from the matched file so the response can include names as well as a count. Otherwise, general-knowledge questions are answered directly without searching the document cache or analyzing files. Other file-oriented questions first search previously indexed, privacy-approved content. If no relevant cached content is found, the app checks Drive for relevant files and only screens, extracts, chunks, and embeds relevant candidates. If no relevant file or content is found, it asks whether you want a general-knowledge answer and only provides one after you confirm. When no title matches, selecting files limits the cache and Drive search to those files.
4. **Review or cancel the answer.** The chat displays the response and available source references. While the request is running, the interface shows its stages: finding relevant files, checking privacy and security, reading content, and generating an answer. Select **Cancel** to stop a request that is still running. If no files were selected, the app uses automatic file discovery.
5. **Review security activity or manage the connection.** Select **Security Audit** to view recorded guardrail events. Use **Sync** to refresh the Drive catalog, or **Disconnect Google Drive** to remove the app's stored Drive connection; you can reconnect later.

The app requests read-only Google Drive access. Connecting Drive does not itself analyze every document: document processing is initiated when a user asks a question.

When a question names a worksheet (for example, `the "Sales Data" sheet`,
`sheet named Sales Data`, or `Give me Sales Data`) in a selected `.xlsx`
workbook, retrieval uses only that exact worksheet. A missing explicitly named
sheet returns a not-found response rather than falling back to other sheets. A
workbook selected in the UI takes precedence over filename-based routing. CSV
files have no worksheets.

## Answer cache

The backend checks a user-scoped PostgreSQL answer cache before Drive catalog,
document retrieval, or model work. Cache keys use the normalized exact query,
intent, selected-file scope, and user ID; general answers, Drive-grounded answers,
insufficient-evidence results, assistant responses, and consent decisions are kept
as separate result types. Drive-grounded entries are reused only while their
indexed source files remain privacy-approved and their recorded Drive versions
match the database. Short configurable expirations limit staleness when Drive
changes have not yet been synchronized. Cached results contain the answer and
source metadata, not extracted document text. Disconnecting Google Drive clears
that user's cached answers. Identical concurrent misses are coalesced within a
backend process; coordination across multiple backend workers is not configured.

After updating an existing database, create the cache table by running
`python init_db.py` from the `backend` directory. The schema setup is safe to
re-run. Cache durations can be configured through `QUERY_ANSWER_CACHE_TTL_SECONDS`,
`GENERAL_ANSWER_CACHE_TTL_SECONDS`, `INSUFFICIENT_ANSWER_CACHE_TTL_SECONDS`, and
`QUERY_DECISION_CACHE_TTL_SECONDS`. Defaults are 60 seconds for document and
assistant answers, 24 hours for general answers, 30 seconds for insufficient
results, and one hour for consent decisions.

The backend logs cache-hit and cache-miss handling durations. A live before/after
latency benchmark and cache-hit rate require a configured database and Google
Drive account; no speedup is claimed without those measurements.
