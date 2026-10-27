# AI-Drive Analyzer

## User Flow

AI-Drive Analyzer lets users ask questions about files in Google Drive. A new user can use it as follows:

1. **Open the app and connect Google Drive.** On the dashboard, select **Connect Google Drive** and sign in with Google. Review the consent screen and grant the requested read-only Drive access; the app needs permission to see and download Drive files to analyze them. After authorization, the dashboard shows the connected account and loads the Drive catalog.
2. **Browse the Drive catalog.** Use the **All Files**, **Docs**, **Sheets**, and **PDFs** tabs or the search field to find documents. Select one or more files to limit a question to those files. Leave the selection empty if you want the app to find relevant files automatically.
3. **Ask a question.** Enter a question in the chat and send it. The app checks Drive file names (not document contents) for title words that appear in the question. If a title matches, that named file takes priority over other selected files. Questions asking for section, chapter, or worksheet/tab inventories read all indexed chunks from the matched file so the response can include names as well as a count. Otherwise, general-knowledge questions are answered directly without searching the document cache or analyzing files. Other file-oriented questions first search previously indexed, privacy-approved content. If no relevant cached content is found, the app checks Drive for relevant files and only screens, extracts, chunks, and embeds relevant candidates. If no relevant file or content is found, it asks whether you want a general-knowledge answer and only provides one after you confirm. When no title matches, selecting files limits the cache and Drive search to those files.
4. **Review or cancel the answer.** The chat displays the response and available source references. While the request is running, the interface shows its stages: finding relevant files, checking privacy and security, reading content, and generating an answer. Select **Cancel** to stop a request that is still running. If no files were selected, the app uses automatic file discovery.
5. **Review security activity or manage the connection.** Select **Security Audit** to view recorded guardrail events. Use **Sync** to refresh the Drive catalog, or **Disconnect Google Drive** to remove the app's stored Drive connection; you can reconnect later.

The app requests read-only Google Drive access. Connecting Drive does not itself analyze every document: document processing is initiated when a user asks a question.
