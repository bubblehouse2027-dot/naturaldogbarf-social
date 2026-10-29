# Natural Dog BARF · automatic publishing to Instagram + Facebook

This repository holds all posts for **2 November 2026 – 7 January 2027** (37 posts: 21 Reels, 9 carousels, 7 images) and a small program that publishes them automatically, at the right Lisbon time, to the **Instagram account** and the **Facebook Page** of Natural Dog BARF.

It runs for free on GitHub: a scheduled job checks every 30 minutes whether a post is due, publishes it through Meta's official Graph API (v26.0), and writes what it published to `state/published.json`.

```
calendar.json                 ← every post: date, time, caption, files, on/off switch
docs/media/                   ← the videos and images (served publicly by GitHub Pages)
publisher/publish.py          ← the publishing program
.github/workflows/publish.yml ← the 30-minute schedule
state/published.json          ← log of what was published (updated automatically)
```

---

## Before you start (checklist)

- [ ] The Instagram account is a **Professional account (Business)**.
- [ ] That Instagram account is **connected to the Natural Dog BARF Facebook Page** (Instagram → Settings → Account type and tools → or in Meta Business Suite → Settings → Linked accounts).
- [ ] You are an **admin of the Facebook Page**.
- [ ] You have a **GitHub account** (free is fine).
- [ ] About **45 minutes** for the first setup.

---

## Step 1 · Create the repository on GitHub

1. Go to github.com → **New repository**.
2. Name: `naturaldogbarf-social`. Visibility: **Public** (needed for free GitHub Pages; the files are posts that will be public anyway; no passwords live in the files).
3. Do **not** add a README (this one is included). Click **Create repository**.

## Step 2 · Upload the files

The easiest way is **GitHub Desktop** (desktop.github.com), because there are many files:

1. In GitHub Desktop: **File → Clone repository** → choose `naturaldogbarf-social` → pick a folder on your computer.
2. Unzip `naturaldogbarf-social.zip` and copy **everything inside it** (including the hidden `.github` folder) into that folder.
3. In GitHub Desktop write a summary ("First upload"), click **Commit to main**, then **Push origin**.

> Uploading through the website also works, but the browser limits each upload to 100 files, so you would need several rounds. The `.github` folder is hidden on Mac (press Cmd+Shift+. in Finder to see it).

## Step 3 · Switch on GitHub Pages (this hosts the media for Meta)

1. In the repository: **Settings → Pages**.
2. **Source:** *Deploy from a branch*. **Branch:** `main`, folder **`/docs`**. Save.
3. After 1–2 minutes the page shows: *Your site is live at* `https://YOUR-USER.github.io/naturaldogbarf-social/`.
4. Test one file in the browser, for example
   `https://YOUR-USER.github.io/naturaldogbarf-social/media/01/01_2026-11-02_reel_isto-e-o-jantar-dele.mp4` — the video should play.

Keep this address: it is your **MEDIA_BASE_URL** (without a slash at the end).

## Step 4 · Create a Meta app

1. Go to **developers.facebook.com** → log in with the Facebook account that is admin of the Page → **My Apps → Create app**.
2. Name it `NDB Publisher`. When asked for the use case or app type, choose the **Business** type / the option for managing Pages and Instagram content. Link it to the Natural Dog BARF business portfolio if asked.
3. Leave the app in **Development mode**. For publishing to your own Page and Instagram account (you are admin of both and of the app) no App Review is needed.

## Step 5 · Get the three IDs and the permanent token

1. Open **Graph API Explorer**: developers.facebook.com/tools/explorer.
2. Top right: select the app **NDB Publisher**. Under *User or Page*: **Get User Access Token**.
3. Tick these permissions and click **Generate Access Token** (approve the Facebook pop-up and select the Natural Dog BARF Page and Instagram account):
   `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `instagram_basic`, `instagram_content_publish`, `business_management`
4. Make the token long-lived: click the blue **i** next to the token → **Open in Access Token Tool** → **Extend Access Token** → copy the new token.
5. Back in Graph API Explorer, paste that long-lived token in the token field and run this query:
   ```
   me/accounts?fields=id,name,access_token,instagram_business_account
   ```
6. In the answer, for the Natural Dog BARF Page, copy:
   - `id` → this is **FB_PAGE_ID**
   - `access_token` → this is **META_PAGE_TOKEN** (a Page token made from a long-lived user token does not expire)
   - `instagram_business_account.id` → this is **IG_USER_ID**

> Check the token in the Access Token Debugger: *Expires* should say **Never**. If you later change your Facebook password or remove the app, repeat step 5 and update the secret.

## Step 6 · Put the settings into GitHub (secrets)

In the repository: **Settings → Secrets and variables → Actions**.

**Secrets** tab → **New repository secret**, three times:

| Name | Value |
| --- | --- |
| `META_PAGE_TOKEN` | the Page access token from step 5 |
| `FB_PAGE_ID` | the Page id |
| `IG_USER_ID` | the Instagram business account id |

**Variables** tab → **New repository variable**:

| Name | Value |
| --- | --- |
| `MEDIA_BASE_URL` | `https://YOUR-USER.github.io/naturaldogbarf-social` |

Secrets are encrypted: nobody can read them back, not even from the code.

## Step 7 · Test (nothing is published yet)

1. Repository → **Actions** tab. If asked, click **I understand my workflows, go ahead and enable them**.
2. Click **Publish scheduled posts → Run workflow**, mode **check** → Run. It must show four `OK` lines (token/Page, Instagram account, publishing quota, media hosting). A `FAIL` line tells you which step to redo.
3. Run again with mode **dry-run**: it lists what would be published right now, without publishing.
4. Optional real test: mode **only**, post `4` (an image), platform `facebook`. Check the Page, then delete the test post there and remove the line for `04` from `state/published.json` (edit the file on GitHub) so it is published again at its date.

**From now on it runs by itself** every 30 minutes. Posts appear at their scheduled Lisbon time, or up to ~30 minutes later (GitHub's scheduler is not to the minute).

---

## Daily use

**Posts on hold.** Two posts are switched off until Paulo confirms the details:

| Post | Date | What to confirm |
| --- | --- | --- |
| #24, #27 | 12 and 17 Dec | Christmas order deadline "até 20 de dezembro" |

When confirmed, open `calendar.json` on GitHub (pencil icon), change `"hold": true` to `"hold": false` for that post and **Commit changes**. If the offer or date is different, ask for new files first.

**Change a caption.** Edit the `caption` of that post in `calendar.json` and commit. Line breaks are written as `\n`.

**Move a post.** Change its `date` (YYYY-MM-DD) or `time` (HH:MM, Lisbon time) in `calendar.json`.

**Publish one post now.** Actions → Run workflow → mode **only**, post number.

**Pause everything.** Actions → Publish scheduled posts → **⋯ → Disable workflow**. Enable it again to resume; posts that became more than 36 hours late are skipped (the log says so) and can be published with mode **only**.

**See what happened.** Actions tab → each run shows a log; `state/published.json` lists every published post with its Instagram/Facebook id and time.

## Limits and good to know

- Instagram allows up to 100 API posts per 24 hours, Facebook 30 Reels per 24 hours. This calendar uses at most 1 post per day.
- Instagram only accepts **JPEG** images through the API; all images here are already JPEG.
- Each Reel has its own track from Pixabay Music (free for commercial use; only tracks without Content ID registration and not AI-generated). See `MUSICA.md` and `CREDITOS_pixabay.txt`. Do not add Instagram music on top.
- Background footage is Pexels stock (free for commercial use). The dogs in it are not customers.
- If a run fails (red ✗ in Actions), GitHub emails you. Open the run, read the `ERROR` line, fix, and use mode **only** for that post.

---

## Manual alternative (Meta Business Suite)

If you prefer not to use the automation, or for a one-off post:

1. Open **business.facebook.com** → Natural Dog BARF → **Planner** (or *Content → Create post* / *Create reel*).
2. Select **both** Facebook and Instagram as destinations.
3. **Reel:** upload the `.mp4` from `docs/media/NN/`; in *Thumbnail* upload the matching `_capa.jpg`.
   **Carousel:** upload the JPEGs of that post in order (01, 02, …).
   **Image:** upload the single JPEG.
4. Copy the caption from `LEGENDAS.md` (same number).
5. Click the arrow next to *Publish* → **Schedule** → set date and time from the calendar → **Schedule**.
6. Do this for all posts in one sitting per month; Business Suite keeps them scheduled.

Do not use both methods for the same post, or it will appear twice.
