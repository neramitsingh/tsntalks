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

`index.json` in each folder lists the ids present. The Pages workflow regenerates
both manifests from the folders on every deploy, so you do not edit them by hand;
the committed copies keep local previews and the test suite honest.
