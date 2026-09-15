# Episode stills

`<youtube_video_id>.jpg` here is the clean frame the site uses for that episode:
on the home page's room (the newest episode that has one) and anywhere a wide
still is wanted. `site/img/faces/<id>.jpg` is the matching 4:5 crop around the
guest, used by the "who has been in the room" strip.

Both are frames from the episode itself, never the YouTube thumbnail: the
thumbnail carries the headline and the guest's name baked in, and the site sets
those in its own type.

**Producing them:** pull five candidate frames per episode (a `frames/` folder
of `<id>-<n>.jpg`), then

    python infra/pick_stills.py <frames_dir>

picks the best frame per episode (a detected face first, then sharpness), writes
the still at 1600px wide (whole: the show's burned-in logo stays and the page
dims it with a vignette) and the face crop. A clean
studio still or portrait from Sunny drops in under the same name and wins.

The detector cannot tell the guest from the host, so `infra/still_picks.json`
carries the hand picks: which candidate frame, and which face in it (`left`,
`right`, `upper`, or an explicit box). Every crop was reviewed against the
episode's own thumbnail on 2026-09-15; when a new episode's crop shows the
wrong person, add a line there and re-run the picker. If the five default
samples never show the guest, pull five more at other points
(`pull_frames.py <dir> <id> --fracs 0.2,0.4,0.55,0.75,0.92 --from 5`).

Three of these stills are also the rate card's reel (`site/partner/index.html`,
`.reel`), chosen by hand because that page is static by design. When a new
episode drops, swap the oldest of the three for its still.

`index.json` in each folder lists the ids present. The Pages workflow regenerates
both manifests from the folders on every deploy, so you do not edit them by hand;
the committed copies keep local previews and the test suite honest.
