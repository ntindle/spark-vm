# Codec-licensing research for the live-machine-control surface

**Status:** research, not legal advice. Research date: 2026-09-20.

Closes the open diligence line in `docs/REMOTE_DESKTOP_TRANSPORT_RESEARCH.md`
§2.2 — *"Codec licensing diligence still owed: H.264 sits in a patent pool,
HEVC's pools are fragmented, AV1 is royalty-free, x264 is GPL — the hosted
product needs a counsel-level answer before committing to a codec"* — for the
#47 transport shortlist (Selkies-GStreamer, Sunshine + Moonlight-Web, Xpra).
This document closes the line **as research**; counsel sign-off remains
required before monetized streaming (see §8).

## 0. What this document is not

Desk research, not legal advice. It collects what patent-pool operators,
licensors, standards bodies, and projects publicly say about the codecs in
play. Every factual claim is labeled **VENDOR-VERIFIED** (pool operator /
licensor / project docs), **THIRD-PARTY** (independent press/docs), or
**INFERRED** (reasoning — verify before acting), with source URLs in §7.
It does not replace a counsel-level patent review.

## 1. The decision this feeds

The #47 desktop surface streams an interactive desktop over WebRTC to a plain
browser. The hosted fleet is CPU-only for the foreseeable future (Fly GPUs
deprecated 2026-07-31, per `docs/GPU_PATH_RESEARCH.md`), so the default codec
must (a) software-encode ~720p30 desktop content on a 2–4 vCPU box, (b) decode
in a stock browser with no plugin, and (c) be legally safe for the operator
to run as a commercial service. The self-hosted product faces only (a)+(b);
there, codec choice is the operator's responsibility, not the repo's.

## 2. Codec-by-codec licensing position

### 2.1 H.264 / AVC

Pool administrator: **Via Licensing Alliance** (Via LA, formerly MPEG LA —
MPEG LA transaction April 2023 brought Mitsubishi Electric aboard; Dolby/GE/
Philips are the other substantial owners) [THIRD-PARTY —
https://ipfray.com/breaking-access-advance-acquires-via-licensing-alliances-hevc-vvc-patent-pools/].
Program page: https://www.via-la.com/licensing-2/avc-h-264/.

Published terms summaries (confirm against current Via LA license text with
counsel — 2010-era summaries may be stale):

- **First 100,000 units per year are royalty-free**; then per-unit royalties
  (historically ~$0.20/unit up to 5M units, $0.10 beyond, annual enterprise
  cap ~$5M) [THIRD-PARTY — x264, LLC licensing summary,
  https://x264.org/wp-content/uploads/2024/04/x264LicensingInfoSheet_04142024b.pdf;
  http://mailman.videolan.org/pipermail/x264-devel/2010-July/007508.html].
- **"Internet Broadcast AVC Video" (video free to end users) is royalty-free
  for the life of the license** per MPEG LA's 2010 announcement — but
  *"products and services other than Internet Broadcast AVC Video continue to
  be royalty-bearing"* (devices, paid title/subscription video,
  shipped encoders/decoders) [THIRD-PARTY —
  https://www.mactech.com/2010/08/27/mpeg-la-offers-h-264-video-license-royalty-free-for-life/,
  https://cdm.link/editorial-mpeg-la-extends-royalty-free-license-for-h-264-sorta-but-not-much-changes/].
  **INFERRED: a paid hosted remote-desktop service is NOT "Internet Broadcast
  AVC Video"** — it sits in a royalty-bearing category.

**Who pays:** the party that makes/uses/distributes the encoder pays, not the
upstream project — *"if Company A uses Company B's encoder in their product,
Company A must pay the fees, not Company B"* [THIRD-PARTY —
http://mailman.videolan.org/pipermail/x264-devel/2010-July/007508.html]. For
the hosted fleet, that is the operator (each host VM running the encoder is
plausibly a "unit"; the 100k-units/yr free threshold is the headroom
argument) [INFERRED — counsel must confirm unit counting].

**2024–2026 changes:** no AVC pool consolidation found this session — Via LA
still administers it. The 2025 consolidation was HEVC/VVC (§2.2). Avanci's
video-licensing program was NOT verified this session (§8 item 7).

**Cisco openh264 grant (decode + encode):** Cisco pays the pool administrator
the full cap for the binary modules **it builds and distributes**; downstream
users of Cisco's binaries are covered. **The grant does NOT travel with the
source — a self-compiled openh264 is outside Cisco's umbrella**
[THIRD-PARTY — reported by eWeek and The Register on Cisco's 2013 announcement:
https://www.eweek.com/networking/cisco-open-sources-h-264-codec-for-web-communications/;
https://www.theregister.com/2013/10/30/cisco_open_source_h264_stack/;
THIRD-PARTY on the self-build exclusion:
https://github.com/phpboyscout/ffmpeg-wasi/blob/HEAD/docs/explanation/licensing.md].
Cisco's stated scope was "effectively free for use in WebRTC"; whether that
extends to hosted remote-desktop streaming is a counsel question (§8 item 3),
and the grant's 2026 currency was not verified this session (§8 item 10).

**openh264 encoder capability:** BSD-2-Clause source [VENDOR-VERIFIED —
https://github.com/cisco/openh264/blob/HEAD/README.md], but the encoder is
**Constrained Baseline Profile only (up to Level 5.2), single reference
frame, no B-frames, 4:2:0 only**. Measurably worse quality-per-bit than x264
at desktop bitrates [INFERRED]. Fine as a compatibility fallback; weak as the
primary codec.

### 2.2 H.265 / HEVC

**The big 2025–2026 change:** on **2025-12-15, Access Advance acquired the
administrator of Via LA's HEVC and VVC patent pools** (renamed the **"VCL
Advance"** program); Via LA continues reporting/distribution for a transition
period while Access Advance assumed overall administration, aiming at a
"one-stop shop" for HEVC/VVC licensing [THIRD-PARTY —
https://ipfray.com/breaking-access-advance-acquires-via-licensing-alliances-hevc-vvc-patent-pools/;
VENDOR boilerplate confirming —
https://www.businesswire.com/news/home/20251221678968/nl]. March-2026: Via's
licensors voted to keep Access Advance as administrator (a Sisvel replacement
proposal failed) [THIRD-PARTY —
https://ipfray.com/vote-to-replace-access-advance-with-sisvel-as-vcl-hevc-vvc-pool-administrator-fails-less-than-1-3-of-licensors-in-favor/].

Current vendor boilerplate: HEVC Advance pool = 29,000+ patents; VVC Advance
= 4,500+; a **Video Distribution Patent Pool** aimed at streaming services
covering **HEVC, VVC, VP9, and AV1**; Multi-Codec Bridging Agreement with a
single discounted HEVC+VVC rate [VENDOR —
https://www.businesswire.com/news/home/20251221810034/fr].

**What fragmentation means for us: mostly moot.** HEVC is not viable for the
product's browser target regardless of patents: Chrome does not support HEVC
in WebRTC at all; only Safari ≥ 17.9 negotiates HEVC over WebRTC
[THIRD-PARTY — Selkies-GStreamer encoder table,
https://github.com/yarikoptic/selkies-gstreamer/blob/HEAD/docs/component.md].
"Decode in a plain browser" rules HEVC out. **Do not pursue HEVC.** Velos
Media's current standing was not verified this session (§8 item 6).

### 2.3 VP8

On **2013-03-07**, Google and MPEG LA announced agreements granting Google a
license to techniques **that may be essential to VP8 and earlier VPx** under
patents of **11 patent holders**, with the right for Google to **sublicense
those techniques to any user of VP8 — whether the implementation is Google's
or another entity's** — plus sublicensing for **one next-generation VPx
codec**. MPEG LA **discontinued its effort to form a VP8 patent pool**
[VENDOR-VERIFIED — full text of the release, reprinted at
https://www.design-reuse.com/news/202523471-google-and-mpeg-la-announce-agreement-covering-vp8-video-format/;
THIRD-PARTY press report:
https://9to5google.com/2013/03/07/google-licenses-mpeg-la-patents-for-vp8-video-format/;
Google's terms note via
https://lists.w3.org/Archives/Public/public-html/2013Mar/0055.html].

**Current standing:** no reversal or new VP8 pool found through 2026-09-20;
the industry treats VP8 as royalty-free [THIRD-PARTY —
https://bloggeek.me/webrtc-h264-video-codec-hardware-support/]. The deal's
terms: [VENDOR-VERIFIED — full text of the Google/MPEG LA release, reprinted:
https://www.design-reuse.com/news/202523471-google-and-mpeg-la-announce-agreement-covering-vp8-video-format/;
announcement reported THIRD-PARTY by
https://9to5google.com/2013/03/07/google-licenses-mpeg-la-patents-for-vp8-video-format/
and Google's own terms note,
https://lists.w3.org/Archives/Public/public-html/2013Mar/0055.html].
The WebM Project's patent-license pages were not re-verified this session
(§8 item 9). The sublicense covers VP8 **implementations by anyone** —
including a server-side encoder the fleet runs — which is the cleanest patent
story of any codec here [INFERRED from the release text].

### 2.4 VP9

Google offers VP9 under the WebM Project's royalty-free patent grant
[THIRD-PARTY —
https://medium.com/@red5-streaming/av1-vs-vp9-vs-vp8-how-to-choose-a-codec-in-2025-f967e6061e30].
Caveats: **Sisvel announced VP9+AV1 patent pools in March 2019**
[THIRD-PARTY — https://www.wowza.com/blog/av1-codec-aomedia-video-1-explained],
and **Access Advance's Video Distribution Patent Pool explicitly covers
VP9** alongside HEVC/VVC/AV1 [VENDOR —
https://www.businesswire.com/news/home/20251221810034/fr]. So VP9's
"royalty-free" is Google-grant royalty-free, not pool-proof. Browser WebRTC
support is Chrome/Firefox only (Safari: no VP8/VP9 in WebRTC), which already
weakens it for us (§5).

### 2.5 AV1

**AOMedia Patent License 1.0** grants each licensee *"a non-sublicensable,
perpetual, worldwide, non-exclusive, no-charge, **royalty-free**, irrevocable
(except as expressly stated) patent license to its **Necessary Claims** to
make, use, sell, offer for sale, import or distribute any Implementation"*
[VENDOR-VERIFIED — the license text itself, §1.1:
https://aomedia.org/license/patent-license/]. Two further terms worth noting:
§1.2.2 states the license is *directly from Licensor to Licensee* — no
rights are received from suppliers or distributors (no pass-through);
§1.3 is a defensive-termination clause (a licensee that asserts an
Implementation infringes Necessary Claims loses the grant).
**Key limit: it covers only AOMedia members' Necessary Claims.**
Third-party claims are now materializing:

- Sisvel launched AV1 (+VP9) pools in 2019 (see §2.4).
- **Dolby sued Snap over AV1 patents** in Brazil and the US (reported March
  2026) [THIRD-PARTY —
  https://ipfray.com/access-advance-issues-call-for-patents-for-potential-av1-av2-pool/].
- **August 2026: Access Advance issued a call for patents for a potential
  AV1/AV2 pool** [THIRD-PARTY — same].
- AOMedia formally released **AV2 1.0** (~June 2026) under the same
  royalty-free patent policy [THIRD-PARTY —
  https://linuxiac.com/aomedia-officially-releases-av2-codec-after-first-1-0-milestone/].

**Browser/decoder adoption (2026):** Chrome supports AV1 **encode** in WebRTC
since Chrome 90 (2021, libaom; Chrome 113 added a "Speed 10" realtime preset
— ~45% better compression than VP9 for screen sharing, ~35% faster) [VENDOR —
https://developer.chrome.com/blog/av1]; Firefox 135+ (2025) AV1 WebRTC encode
on by default (libaom) [THIRD-PARTY —
https://github.com/iohzrd/echocell/blob/HEAD/todos/av1-codec-support.md];
**Safari 18.4+ AV1 WebRTC is experimental and hardware-gated (M3+/A17 Pro+
only)** — older Apple devices fall back [THIRD-PARTY — same]. Hardware AV1
decode is common on GPUs from ~2020+; software decode (dav1d) is fine on
desktops [THIRD-PARTY — https://www.red5.net/blog/av1-webrtc-streaming/].

**Encode cost (the fleet constraint):** AV1 software encode is **10–30× more
CPU-intensive than VP8**; SVT-AV1's fastest presets (10–12) can do realtime
1080p30 on a beefy box [THIRD-PARTY —
https://github.com/iohzrd/echocell/blob/HEAD/todos/av1-codec-support.md].
**INFERRED: on a 2–4 vCPU host with no GPU, realtime low-latency 720p30 AV1
desktop encode is marginal at best and leaves no headroom** — engineering
must benchmark, but AV1 is not the primary choice for the CPU-only fleet.

### 2.6 Encoder-side licensing (x264, openh264)

**x264** — GNU **GPL v2 or later**; a **commercial license from x264, LLC**
is the alternative (info sheet eff. 2022, PDF updated 2024-04-14; VideoLAN /
FFmpeg cannot grant commercial licenses) [VENDOR-VERIFIED —
https://x264.org/technology/;
https://x264.org/wp-content/uploads/2024/04/x264LicensingInfoSheet_04142024b.pdf].
Per x264, LLC's own summary: server-side-only use that is **not distributed
to customers needs no commercial license**; a proprietary distributed product
linking x264 does [THIRD-PARTY —
http://mailman.videolan.org/pipermail/x264-devel/2010-July/007508.html].
**INFERRED consequences for spark-vm:** (a) the fleet's x264 runs
server-side — the copyright side is manageable for an MIT repo provided
x264 binaries are not *distributed* in shipped images without a GPL
compliance plan; (b) **the GPL is a copyright license and conveys no patent
rights — the AVC pool obligation is separate and still applies**
[THIRD-PARTY —
https://github.com/phpboyscout/ffmpeg-wasi/blob/HEAD/docs/explanation/licensing.md].

GStreamer `x264enc` lives in gst-plugins-ugly and links the GPL library:
shipping it in a distributed container image is distribution of GPL
software (source-offer obligations attach). Shipping *configuration/docs
that select* x264enc (as Selkies does) is a lighter act [INFERRED — counsel].

**openh264** — **BSD-2-Clause** source [VENDOR-VERIFIED —
https://github.com/cisco/openh264]; GStreamer `openh264enc` exists as a
software H.264 encoder [THIRD-PARTY —
https://github.com/yarikoptic/selkies-gstreamer/blob/HEAD/docs/component.md].
Copyright-clean for MIT, but (1) self-compiled builds sit outside Cisco's
patent grant (§2.1); (2) encoder is Constrained Baseline, no B-frames — a
quality/cost penalty (§2.1).

## 3. Comparison table

| Codec | Patent posture (2026) | Software encode @720p30, CPU-only | Browser decode | WebRTC MTI | MIT-repo fit |
|---|---|---|---|---|---|
| **H.264 via x264enc** | AVC pool (Via LA); 100k units/yr royalty-free threshold in published summaries; paid service = royalty-bearing category | ✅ x264 ultrafast/veryfast ≈ 1–2 cores [INFERRED — benchmark] | ✅ all browsers incl. Safari/iOS | ✅ | ⚠️ GPL encoder binary in shipped images needs a GPL compliance plan; config-only selection is fine |
| **H.264 via openh264enc** | Same AVC pool; Cisco grant covers **only Cisco-built binaries** | ✅ light | ✅ all browsers | ✅ | ✅ BSD source; self-build sits outside Cisco's grant |
| **VP8** | 2013 Google–MPEG LA sublicense to **any implementer**; no pool formed; cleanest story | ✅ libvpx realtime ≈ cheap | ⚠️ all except Safari/iOS | ✅ | ✅ BSD (libvpx) |
| **VP9** | Google grant, but Sisvel pools + Access Advance VDP pool cover it | ⚠️ heavier than VP8, lighter than AV1 | ⚠️ Chrome/Firefox only | ❌ optional | ✅ BSD (libvpx) |
| **AV1** | AOMedia RF grant (members only) + Sisvel/Access-Advance pool shadow + Dolby v. Snap (2026) | ❌ 10–30× VP8; marginal on 2–4 vCPU | ⚠️ Chrome/FF; Safari 18.4+ experimental HW-gated | ❌ optional | ✅ BSD (libaom/SVT-AV1/dav1d) |
| **HEVC** | Consolidating under Access Advance (VCL Advance, Dec 2025); royalty-bearing | ⚠️ x265 software heavy | ❌ Safari ≥17.9 only (WebRTC) | ❌ | ⚠️ GPL (x265) + pool |

## 4. Browser reality for WebRTC (2026)

**Mandatory-to-implement (RFC 7741/7742, 2016): VP8 and H.264 (Constrained
Baseline).** In practice: Chrome, Firefox, Edge implement both; **Safari
implements H.264 only — no VP8/VP9 in WebRTC** [THIRD-PARTY —
https://bloggeek.me/webrtc-h264-video-codec-hardware-support/;
https://bugs.webkit.org/show_bug.cgi?id=173141;
https://www.nojitter.com/video-conferencing/5-factors-to-consider-for-your-webrtc-project].
**All iOS browsers are WebKit → Safari's H.264-only constraint applies to
all of iOS.** AV1 is an RTP-payload RFC (RFC 9134, 2022) and an *optional*
WebRTC codec: Chrome 113+ / Firefox 135+ ship it; Safari 18.4+ experimental,
hardware-gated (§2.5).

**Net for "decode in a plain browser": H.264 is the only codec that works in
*every* major browser, including all of iOS.** VP8 works everywhere except
Safari/iOS. AV1 works in Chrome/Firefox desktop, partially in Safari. HEVC
works only in Safari. **H.264 maximizes client reach.**

## 5. What comparable OSS projects choose

One line each, with source. **Sourcing caveat:** the project-position claims
below are a single-source aggregation — the third-party community doc cited
for each; the projects' own docs were not checked this session. Primary
sourcing is a follow-up before these positions harden into architecture
decisions.

- **Selkies-GStreamer:** default/recommended software encoder is **x264enc**
  (GPL); `vp8enc` "recommended under 2K" — accepts a GPL encoder for quality;
  GStreamer pluggability throughout [THIRD-PARTY —
  https://github.com/yarikoptic/selkies-gstreamer/blob/HEAD/docs/component.md].
- **Sunshine:** H.264 default; HEVC, AV1 offered (hardware) — H.264 for
  multi-vendor hardware ubiquity and maximum device reach; AV1 only where
  hardware exists [THIRD-PARTY —
  https://github.com/aislopware/aislopdesk/blob/HEAD/docs/09-codec-choice.md].
- **Moonlight (clients):** H.264/HEVC/AV1 per client capability —
  client-driven negotiation; web client uses WebCodecs for all three
  [THIRD-PARTY — https://github.com/nuh03/moonlight-web].
- **Parsec:** H.264 default; HEVC+AV1 options (4:4:4 paid tier) —
  "H.264-for-latency" cross-vendor conclusion [THIRD-PARTY —
  https://github.com/aislopware/aislopdesk/blob/HEAD/docs/09-codec-choice.md].
- **NVIDIA GeForce Now:** H.264 → HEVC → AV1 progression — hardware-encodes
  each generation as GPUs adopt it [THIRD-PARTY —
  https://github.com/aislopware/aislopdesk/blob/HEAD/docs/09-codec-choice.md].
- **Steam Remote Play:** H.264 default, HEVC where supported — maximizes
  device reach [THIRD-PARTY —
  https://github.com/aislopware/aislopdesk/blob/HEAD/docs/09-codec-choice.md].

Pattern: **everyone whose client is "a browser / arbitrary device" defaults
to H.264 and treats newer codecs as opt-in hardware paths.** Nobody with a
browser client defaults to AV1 or HEVC for the base tier.

## 6. Recommendation

**(a) Hosted CPU-only fleet: H.264 Baseline via `x264enc`
(ultrafast/veryfast, ~720p30) as the primary software path.** Rationale:
only codec decodable in *every* browser (Safari/iOS has no VP8); cheapest
software encode that fits 2–4 vCPU at low latency; patent exposure is the
well-trodden AVC pool with a published 100k-units/yr royalty-free threshold
a small fleet sits under. Keep **`openh264enc` as a config fallback** and
**VP8 as a secondary negotiated option** for non-Apple clients where patent
posture is preferred. **Do not ship AV1 or HEVC for the CPU-only tier**
(encode cost; Safari gaps). When GPU hosts exist later, add NVENC/VAAPI
H.264 → AV1 exactly the way Sunshine/Parsec do.

**Gate on counsel (§8 items 1–2): this primary-path recommendation is the
research answer, not an approval to build on.** Do not bake `x264enc` (or
`gst-plugins-ugly`) into fleet golden images, and do not ship monetized
streams, until counsel items 1–2 are answered — they determine both the
AVC-pool royalty position (unit counting; whether a paid remote-desktop
service is "Internet Broadcast AVC Video") and the GPL distribution question
for the image builder. The golden-image recipe is an H4 input, so this
question will resurface when H4 unblocks. H.264 desktop bitrates also feed
the TURN-relay bandwidth model in the transport doc §5.2.

**(b) Self-hosted users:** document the same ladder in the repo: `x264enc`
(default) → `openh264enc` (BSD, lower quality) → `vp8enc` (best patent
story, no Safari) → hardware `nvh264enc`/`vah264enc` when a GPU exists. Keep
the repo MIT-clean by **selecting encoders via config** and documenting which
shipped images contain GPL components (x264enc) — not by pretending the MIT
license covers them.

**Prototype gate (for the #47 bake-off, `docs/REMOTE_DESKTOP_TRANSPORT_RESEARCH.md`
§7):** the prototype must measure, not assume, x264 `ultrafast` 720p30 CPU
cost on a 2–4 vCPU box and glass-to-glass latency with each candidate codec
behind the Selkies-GStreamer default.

## 7. Claimable vs. forbidden claims

The product **may** say (with the cited caveat attached):

- "AV1 is licensed royalty-free by Alliance for Open Media members under the
  AOMedia Patent License 1.0 — a grant that covers members' patents only;
  third-party pools (Sisvel; Access Advance's in-formation AV1 pool) exist."
- "VP8 implementers are covered by the 2013 Google–MPEG LA sublicense
  framework, which extends to any VP8 implementation (per the 2013
  announcement's terms; WebM license pages not re-verified — §8 item 9)."
- "The AVC patent pool's published licensing summaries include a 100,000
  units/year royalty-free threshold (confirm current Via LA terms with
  counsel)."
- "openh264 source is BSD-2-Clause; Cisco's patent grant covers only
  Cisco-built binary modules."

The product **must not** say:

- ❌ "H.264 is royalty-free / free to use" (unqualified).
- ❌ "AV1 is patent-safe / fully royalty-free."
- ❌ "Cisco covers our openh264 build."
- ❌ "x264 is GPL so patents don't apply."
- ❌ Anything implying counsel has signed off.

## 8. Counsel-level sign-off still owed (do not monetize before these)

1. **Current Via LA AVC license text:** confirm the 100k-units/yr threshold
   still stands, how a "unit" is counted for a hosted fleet (per VM? per
   concurrent encoder? per customer?), and that a *paid* remote-desktop
   service falls outside "Internet Broadcast AVC Video."
2. **x264 on the fleet:** does server-side-only use (no binary distribution)
   keep us clear of commercial-license need, and what GPL-compliance duties
   attach if any distributed image contains `x264enc`.
3. **Cisco openh264 binary grant scope:** if the fleet installs Cisco's
   prebuilt openh264 binaries, does the grant cover hosted remote-desktop
   streaming (the 2013 framing was WebRTC calls)?
4. **AV1 third-party exposure:** status of Sisvel's AV1 pool, Access Advance's
   2026 AV1/AV2 pool formation, and the Dolby v. Snap (2026) litigation
   trajectory — needed before any AV1 commitment.
5. **VP9 pool exposure** via Access Advance's Video Distribution Patent Pool.
6. **Velos Media** current standing (not verified this session).
7. **Avanci's video program** — existence/scope not verified this session.
8. **Jurisdiction:** fleet regions (US vs EU software-patent differences).
9. **WebM Project patent-license pages** (VP8/VP9) — re-verify current text.
10. **Cisco openh264 grant currency:** every source verifying the grant's
    terms this session is 2013-era — confirm the royalty arrangement is
    still active in 2026 and Cisco still distributes prebuilt binaries with
    the cap paid.

## 9. Sources

Accessed 2026-09-20 unless noted. Labels: V = VENDOR-VERIFIED, T =
THIRD-PARTY, I = INFERRED.

- Via LA AVC program page (V) — https://www.via-la.com/licensing-2/avc-h-264/
- ip fray: Access Advance acquires Via LA HEVC/VVC pools, 2025-12-15 (T) —
  https://ipfray.com/breaking-access-advance-acquires-via-licensing-alliances-hevc-vvc-patent-pools/
- Business Wire: Access Advance acquisition confirmation (V) —
  https://www.businesswire.com/news/home/20251221678968/nl
- Business Wire: Access Advance pool portfolio boilerplate (V) —
  https://www.businesswire.com/news/home/20251221810034/fr
- ip fray: Sisvel replacement vote fails, March 2026 (T) —
  https://ipfray.com/vote-to-replace-access-advance-with-sisvel-as-vcl-hevc-vvc-pool-administrator-fails-less-than-1-3-of-licensors-in-favor/
- x264, LLC licensing info sheet 2024-04-14 (V) —
  https://x264.org/wp-content/uploads/2024/04/x264LicensingInfoSheet_04142024b.pdf
- x264, LLC — https://x264.org/technology/ (V)
- x264-devel mailing list on license structure (T) —
  http://mailman.videolan.org/pipermail/x264-devel/2010-July/007508.html
- MacTech: MPEG LA H.264 royalty-free-for-life announcement, 2010-08 (T) —
  https://www.mactech.com/2010/08/27/mpeg-la-offers-h-264-video-license-royalty-free-for-life/
- CDM: MPEG LA extends royalty-free H.264 license analysis (T) —
  https://cdm.link/editorial-mpeg-la-extends-royalty-free-license-for-h-264-sorta-but-not-much-changes/
- eWeek: Cisco open-sources H.264 codec, 2013 (V — Cisco announcement via) —
  https://www.eweek.com/networking/cisco-open-sources-h-264-codec-for-web-communications/
- The Register: Cisco open-source H.264 stack, 2013 (V) —
  https://www.theregister.com/2013/10/30/cisco_open_source_h264_stack/
- ffmpeg-wasi licensing explainer on Cisco grant self-build exclusion (T) —
  https://github.com/phpboyscout/ffmpeg-wasi/blob/HEAD/docs/explanation/licensing.md
- openh264 README (V) — https://github.com/cisco/openh264/blob/HEAD/README.md
- 9to5Google: Google licenses MPEG LA patents for VP8, 2013-03-07 (V) —
  https://9to5google.com/2013/03/07/google-licenses-mpeg-la-patents-for-vp8-video-format/
- Design-Reuse: Google/MPEG LA VP8 agreement full text (V) —
  https://www.design-reuse.com/news/202523471-google-and-mpeg-la-announce-agreement-covering-vp8-video-format/
- W3C public-html list: VP8 terms note (V) —
  https://lists.w3.org/Archives/Public/public-html/2013Mar/0055.html
- bloggeek: WebRTC H.264 video codec hardware support (T) —
  https://bloggeek.me/webrtc-h264-video-codec-hardware-support/
- Red5: AV1 vs VP9 vs VP8 codec choice (T) —
  https://medium.com/@red5-streaming/av1-vs-vp9-vs-vp8-how-to-choose-a-codec-in-2025-f967e6061e30
- Wowza: AV1 codec AOMedia Video 1 explained (T) —
  https://www.wowza.com/blog/av1-codec-aomedia-video-1-explained
- ip fray: Access Advance issues call for patents for potential AV1/AV2 pool,
  Aug 2026 (T) —
  https://ipfray.com/access-advance-issues-call-for-patents-for-potential-av1-av2-pool/
- Linuxiac: AOMedia releases AV2 1.0 (T) —
  https://linuxiac.com/aomedia-officially-releases-av2-codec-after-first-1-0-milestone/
- Chrome Developers: AV1 video encode in WebRTC (V) —
  https://developer.chrome.com/blog/av1
- echocell AV1 codec support notes (T) —
  https://github.com/iohzrd/echocell/blob/HEAD/todos/av1-codec-support.md
- Red5: AV1 WebRTC streaming (T) — https://www.red5.net/blog/av1-webrtc-streaming/
- aether-premiere AV1 importer README quoting AOM patent license (V) —
  https://github.com/neohade/aether-premiere-av1-vp9-importer/blob/HEAD/README.md
- Selkies-GStreamer component docs — encoder table (T) —
  https://github.com/yarikoptic/selkies-gstreamer/blob/HEAD/docs/component.md
- NoJitter: 5 factors to consider for your WebRTC project (T) —
  https://www.nojitter.com/video-conferencing/5-factors-to-consider-for-your-webrtc-project
- WebKit bug 173141 — VP8 in Safari WebRTC (T) —
  https://bugs.webkit.org/show_bug.cgi?id=173141
- aislopdesk codec-choice doc — Sunshine/Parsec/Steam/GFN comparisons (T) —
  https://github.com/aislopware/aislopdesk/blob/HEAD/docs/09-codec-choice.md
- moonlight-web (T) — https://github.com/nuh03/moonlight-web
