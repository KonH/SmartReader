# Flow

This document describes the end-to-end processing flow of SmartReader.

---

## Trigger

The flow can be initiated in two ways:

| Mode | Description |
|------|-------------|
| **Ask (pull)** | The user manually requests a content update |
| **Cron (push)** | A scheduled job automatically triggers the pipeline |

---

## Pipeline Steps

```
Ask (pull)  ─┐
              ├──► Read sources ──► Scoring (level 1) ──► Select top N ──► Summarize ──► Scoring (level 2) ──► Show ──► Receive feedback
Cron (push) ─┘                          ▲                                                                              │
                                         │                                                                              │
                                         └──────────────────────── Interests ◄──────────────────────────────────────────┘
```

---

## Step Descriptions

### 1. Read Sources
Fetches new content from all configured sources (RSS feeds, Telegram channels) since the last read timestamp.

### 2. Scoring (Level 1) — Coarse Filter
Each content item is scored based on the user's current **Interests** profile using keyword matching. This is a fast, lightweight pass intended to filter out irrelevant content before expensive operations.

### 3. Select Top N
Only the top-scoring N items from Level 1 are passed forward for further processing. N is configurable.

### 4. Summarize
Each selected item is summarized using the OpenAI API, reducing it to a concise, readable form.

### 5. Scoring (Level 2) — Fine Filter
Summarized content is scored again for relevance. This pass works on the cleaner summarized text and can more accurately assess relevance.

### 6. Show
The final ranked content list is presented to the user via the configured UI (terminal or Telegram).

### 7. Receive Feedback
The user provides feedback (e.g. scores individual items). This feedback is used to update the **Interests** profile.

---

## Feedback Loop

User feedback from the **Receive feedback** step updates the **Interests** store, which feeds back into **Scoring (Level 1)** on the next run. This creates a reinforcement loop where the system continuously improves its relevance ranking based on user behavior.

```
Receive feedback ──► Interests ──► Scoring (level 1)
```
