# Enigma SAC Web

The web application provides the end-to-end user workflow for NASA PSI dataset discovery:

1. Submit a natural-language search.
2. Review every eligible numerical dataset returned by the API.
3. Select a dataset and inspect its schema.
4. Generate an evidence-based summary.
5. Configure and preview a chart from the selected dataset.

## Local development

From the repository root:

```bash
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1 npm run dev --workspace=@enigma-sac/web
```

The application is available at `http://localhost:3000`.

The API URL can be configured with `NEXT_PUBLIC_API_URL`. The frontend never accepts an arbitrary
data URL for server-side access; dataset access remains controlled by the API connectors.

## Production build

```bash
npm run build --workspace=@enigma-sac/web
npm run start --workspace=@enigma-sac/web
```
