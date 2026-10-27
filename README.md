# AI-Drive Analyzer

## User Flow

AI-Drive Analyzer lets users ask questions about files in Google Drive. A new user can use it as follows:

1. **Open the app and connect Google Drive.** On the dashboard, select **Connect Google Drive** and sign in with Google. Review the consent screen and grant the requested read-only Drive access; the app needs permission to see and download Drive files to analyze them. After authorization, the dashboard shows the connected account and loads the Drive catalog.
2. **Browse the Drive catalog.** Use the **All Files**, **Docs**, **Sheets**, and **PDFs** tabs or the search field to find documents. Select one or more files to limit a question to those files. Leave the selection empty if you want the app to find relevant files automatically.
3. **Ask a question.** Enter a question in the chat and send it. Questions about supported file formats are answered directly without accessing Drive. For document questions, the app identifies the request type (such as a fact question, summary, comparison, list, or calculation) to shape the response, searches for candidate files, runs privacy and confidentiality checks, and processes eligible document content on demand. Confidential files identified by those checks are excluded from the answer-generation step. The Drive catalog is cached briefly between queries to reduce repeat API calls, and independent document inspections run concurrently with a small limit.
4. **Review or cancel the answer.** The chat displays the response and available source references. While the request is running, the interface shows its stages: finding relevant files, checking privacy and security, reading content, and generating an answer. Select **Cancel** to stop a request that is still running. If no files were selected, the app uses automatic file discovery.
5. **Review security activity or manage the connection.** Select **Security Audit** to view recorded guardrail events. Use **Sync** to refresh the Drive catalog, or **Disconnect Google Drive** to remove the app's stored Drive connection; you can reconnect later.

The app requests read-only Google Drive access. Connecting Drive does not itself analyze every document: document processing is initiated when a user asks a question.
