# Episode still overrides

Drop a file here named `<youtube_video_id>.jpg` and the site uses it instead of
the YouTube thumbnail for that episode — on the hero and on the poster wall.

Example: `puiF1eGZ2LY.jpg` overrides the still for S2 E7.

**Why:** YouTube thumbnails have the guest's name and "TSN TALKS" baked into the
image, so they fight the page's own typography. The hero scrim is heavy to cope
with that. Clean studio stills from Sunny replace them one at a time, with no
code change.

**Sizing:** 1920×1080 or larger, JPEG, under 400 KB. The hero crops to
`object-position: 70% 30%`, so keep the guest right of centre and high in frame.

## index.json

`index.json` lists the ids that have an override. The Pages workflow regenerates
it from this folder on every deploy, so you do not edit it by hand — but the
committed copy keeps local previews honest. Without it the page would fire a 404
for every episode, probing for files that are usually absent.
