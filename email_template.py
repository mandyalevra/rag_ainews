def build_email_html(digest: dict) -> str:
    cat_colors = {
        "tools": {"bg": "#FFD6E7", "ink": "#5A0F36", "deep": "#E8369A"},
        "money": {"bg": "#E4D9FF", "ink": "#2F1A6E", "deep": "#7C4DFF"},
        "world": {"bg": "#DEFF8C", "ink": "#2A3A00", "deep": "#6B9E00"},
    }

    stories_html = ""
    for cat in digest["categories"]:
        c = cat_colors.get(cat["id"], cat_colors["tools"])
        story_rows = ""
        for i, s in enumerate(cat["stories"]):
            story_rows += f"""
            <tr>
              <td style="padding:16px 0;border-bottom:1px solid #f0ebe6;">
                <table width="100%" cellpadding="0" cellspacing="0">
                  <tr>
                    <td width="32" valign="top" style="padding-right:14px;">
                      <div style="width:28px;height:28px;border-radius:50%;background:{c['deep']};
                                  color:#fff;font-family:monospace;font-size:11px;font-weight:600;
                                  text-align:center;line-height:28px;">{str(i+1).zfill(2)}</div>
                    </td>
                    <td valign="top">
                      <p style="margin:0 0 6px;font-family:Georgia,serif;font-size:17px;
                                 line-height:1.3;color:#1A1613;font-weight:400;">
                        <strong style="font-weight:600;">{s['title']}</strong>
                      </p>
                      <p style="margin:0 0 8px;font-size:14px;line-height:1.6;color:#3d3530;">
                        {s['summary']}
                      </p>
                      <a href="{s['url']}" style="display:inline-block;font-family:monospace;
                                font-size:11px;color:{c['deep']};text-decoration:none;
                                padding:4px 10px;border:1px solid {c['deep']};border-radius:999px;
                                letter-spacing:0.04em;">
                        {s['source']} →
                      </a>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>"""

        stories_html += f"""
        <tr>
          <td style="padding:32px 0 8px;">
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="background:{c['bg']};border-radius:16px;border:1.5px solid #1A1613;
                          box-shadow:4px 4px 0 #1A1613;">
              <tr>
                <td style="padding:24px 28px 20px;">
                  <p style="margin:0 0 4px;font-family:monospace;font-size:11px;
                             letter-spacing:0.1em;text-transform:uppercase;color:{c['ink']};
                             opacity:0.7;">{cat['tagline']}</p>
                  <p style="margin:0;font-family:Georgia,serif;font-size:28px;
                             color:{c['ink']};font-weight:400;line-height:1;">
                    {cat['emoji']} {cat['name']}
                  </p>
                </td>
              </tr>
              <tr>
                <td style="padding:0 28px 24px;">
                  <table width="100%" cellpadding="0" cellspacing="0">
                    {story_rows}
                  </table>
                </td>
              </tr>
            </table>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>by mandy, daily — {digest['date']}</title>
</head>
<body style="margin:0;padding:0;background:#f5f0eb;font-family:'Helvetica Neue',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f0eb;padding:32px 16px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0"
               style="max-width:600px;width:100%;background:#FBF7F4;
                      border-radius:24px;border:1.5px solid #1A1613;
                      box-shadow:6px 6px 0 #1A1613;overflow:hidden;">

          <!-- Header -->
          <tr>
            <td style="background:#1A1613;padding:28px 36px;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <p style="margin:0;font-family:monospace;font-size:18px;
                               font-weight:600;color:#FBF7F4;letter-spacing:-0.02em;">
                      by mandy, daily ✦
                    </p>
                    <p style="margin:4px 0 0;font-family:monospace;font-size:11px;
                               color:rgba(251,247,244,0.55);">
                      an AI digest, written like a friend
                    </p>
                  </td>
                  <td align="right" valign="middle">
                    <p style="margin:0;font-family:monospace;font-size:11px;
                               color:rgba(251,247,244,0.6);letter-spacing:0.04em;">
                      {digest['weekday'].upper()} · {digest['date'].upper()}
                    </p>
                    <p style="margin:4px 0 0;font-family:monospace;font-size:10px;
                               color:rgba(251,247,244,0.4);">
                      ISSUE #{digest['issue']} · {digest['readMin']} MIN READ
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Hero -->
          <tr>
            <td style="padding:36px 36px 0;">
              <p style="margin:0 0 20px;font-family:Georgia,serif;
                         font-size:clamp(32px,6vw,48px);line-height:1.05;
                         font-weight:400;color:#1A1613;letter-spacing:-0.02em;">
                Today, <em style="background:#FFD6E7;padding:0 6px;border-radius:4px;
                                   color:#5A0F36;font-style:italic;">
                  {digest['headline']}
                </em>.
              </p>

              <!-- TL;DR -->
              <table width="100%" cellpadding="0" cellspacing="0"
                     style="background:color-mix(in srgb,#FFD6E7 30%,#FBF7F4);
                            border:1.5px solid #1A1613;border-radius:14px;
                            box-shadow:5px 5px 0 #1A1613;margin-bottom:8px;">
                <tr>
                  <td style="padding:20px 24px;">
                    <p style="margin:0 0 10px;">
                      <span style="display:inline-block;font-family:monospace;font-size:11px;
                                   font-weight:600;letter-spacing:0.1em;text-transform:uppercase;
                                   background:#1A1613;color:#FBF7F4;
                                   padding:4px 10px;border-radius:999px;">
                        TL;DR ✦
                      </span>
                    </p>
                    <p style="margin:0;font-family:Georgia,serif;font-size:18px;
                               line-height:1.45;color:#1A1613;">
                      {digest['tldr']}
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Stories -->
          <tr>
            <td style="padding:0 36px 36px;">
              <table width="100%" cellpadding="0" cellspacing="0">
                {stories_html}
              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="border-top:1px solid #e8e2dc;padding:24px 36px;
                        background:color-mix(in srgb,#1A1613 4%,#FBF7F4);">
              <p style="margin:0;font-family:monospace;font-size:11px;
                         color:rgba(26,22,19,0.5);text-align:center;line-height:1.6;">
                by mandy, daily — built with curiosity ·
                <a href="http://localhost:8080" style="color:rgba(26,22,19,0.5);">
                  read in browser
                </a>
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
