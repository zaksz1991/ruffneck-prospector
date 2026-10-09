# RuffNeck Capture – Chrome Extension

One-click capture of **LinkedIn profiles** and **Google Maps businesses** into RuffNeck Prospector.

## Install (Developer Mode)

1. Open Chrome → `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select this `chrome-extension` folder

## Usage

1. Make sure RuffNeck API is running (`http://localhost:8000`)
2. Open a LinkedIn profile (`linkedin.com/in/...`) or a Google Maps place
3. Click the RuffNeck extension icon
4. (Optional) Set Workspace ID to drop the lead into a shared team workspace
5. Click **Capture to RuffNeck**

The lead is sent to the API, enriched, and appears in Prospects / Pipeline.

## Settings

- **API Base URL** – default `http://localhost:8000`
- **Workspace ID** – optional, assigns the captured lead to a team workspace

Settings are saved in Chrome sync storage.
