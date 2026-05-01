# Meals of Love Guide Generator
### Ronald McDonald House Orange County

Volunteer groups who cook for RMH families need to know what 
to prepare before they shop. Coordinators know what families 
need but spend time manually briefing every group.

This tool closes that gap.

A coordinator updates current resident information once a week 
(dietary restrictions, family count, age ranges). The app pulls 
upcoming volunteer bookings automatically from Microsoft Bookings, 
combines both data sources, and streams a personalized preparation 
guide via Claude — including menu suggestions, a shopping list, 
logistics, and guidance on connecting with families.

Built for the Orange County chapter, which uses Microsoft Bookings 
for volunteer scheduling. The same architecture works for any RMH 
chapter.

---

**Services supported (mapped to current OC chapter services)**
| Service | Duration | Guide includes |
|---------|----------|----------------|
| Meal of Love | 4 hrs | Menu, shopping list, logistics, family connection tips |
| Happy Snacks | 2 hrs | Nut-free snack ideas, individual packaging, quick logistics |
| McBakers | 2 hrs | Allergy-aware baked goods, hospital-friendly packaging |

**Stack:** Python · FastAPI · Microsoft Graph API · 
Claude API (claude-sonnet-4-20250514) · Vanilla HTML/CSS/JS

**Demo mode:** Runs with sample bookings if Azure credentials 
aren't configured — full workflow explorable immediately.
