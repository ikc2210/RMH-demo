import anthropic
import json
from typing import AsyncGenerator

SYSTEM_PROMPT = """You are a warm, experienced Ronald McDonald House volunteer coordinator. \
You deeply care about both the volunteer experience and the families being served. \
You never share family names or identifying information — only anonymized dietary and preference information. \
Your preparation guides are practical, specific, and feel like they were written by someone who has \
personally done this work many times. Every guide should make volunteers feel prepared, welcomed, and \
excited to serve. Use a friendly, personal tone — not corporate or clinical. Use clear headers and \
formatting so the guide is easy to skim while shopping or cooking."""


def _build_meal_of_love_prompt(booking: dict, residents: dict) -> str:
    return f"""Generate a complete Meal of Love Volunteer Preparation Guide for the following group and families.

## Volunteer Group Info
- Group name: {booking['group_name']}
- Date and time: {booking['start_display']}
- Number of volunteers: {booking['num_volunteers'] or 'Not specified'}
- Duration: {booking['duration_hours']} hours
- Volunteer dietary restrictions: {booking['volunteer_dietary'] or 'None reported'}
- First time at RMH: {'Yes' if booking['first_time'] else 'No'}
- Group notes from booking: {booking['group_notes'] or 'None'}

## Current Resident Families at RMH-OC
- Number of families currently staying: {residents.get('num_families', 'Not specified')}
- Total people to cook for: {residents.get('total_people', 'Not specified')}
- Children breakdown: {residents.get('children_breakdown') or 'Not specified'}
- Dietary restrictions and allergies among residents: {residents.get('dietary_restrictions') or 'None reported'}
- Cultural food preferences: {residents.get('cultural_preferences') or 'None noted'}
- Families who typically join dinner in person: {residents.get('families_joining_dinner', 'Not specified')}
- Coordinator notes for this week: {residents.get('volunteer_notes') or 'None'}

---

Generate a warm, practical Meal of Love Preparation Guide with these exact sections:

# Meals of Love Preparation Guide
## {booking['group_name']} · {booking['start_display']}

### Who You're Cooking For Tonight
Describe the people — number of adults and children, age ranges, how many usually sit down for dinner together. Make it feel human. Mention dietary restrictions and allergies clearly and specifically, with callout formatting for anything severe (e.g., **⚠️ NUT-FREE KITCHEN — please check every label**). Note cultural preferences warmly.

### Menu Suggestions
Offer 2–3 specific, complete meal ideas that work for: the group size, cooking experience level {'(first-timers, so keep it accessible)' if booking['first_time'] else '(experienced group)'}, family dietary needs, cultural preferences, and a 4-hour window. For each meal idea include:
- Full menu (main + sides + something simple for kids)
- Estimated prep and cook time
- Difficulty level
- Why it works well for these families tonight

### Shopping List
Consolidated shopping list for your top recommended menu. Include:
- Specific quantities based on cooking for {residents.get('total_people', 'the families')} people
- Organized by store section (Produce, Meat/Protein, Dairy, Pantry, etc.)
- ✓ mark items RMH already stocks (basic oils, salt, pepper, basic spices, sugar, flour)
- Bold any allergy-critical items to double-check

### Logistics & Timeline
- Arrival: Recommend arriving 30 minutes before serving time
- What RMH provides: kitchen equipment, serving dishes, basic pantry staples
- Serving time and expectations
- Cleanup expectations
- Practical time breakdown for a {booking['duration_hours']}-hour shift

### Connecting With Families
Write this section with genuine warmth. Cover:
- How to create a welcoming atmosphere without being overwhelming
- Let families set the tone — some will want to chat, some need quiet dignity
- What to do when children want to help or are curious in the kitchen
- Emotional preparation: what volunteers often feel, and that it's okay
- House rules around photos, noise, and privacy (be firm but kind)

{'### First-Timer Tips' + chr(10) + "Since this is your group's first visit, include a special section with: what volunteers say they wish they knew before their first visit, how to handle the emotions that often come up, what makes a really memorable visit for families, and one or two stories (anonymized) that capture the spirit of the work." if booking['first_time'] else ''}

End with a short, sincere closing that sends the group off with heart. Sign it from "The RMH-OC Team".
"""


def _build_happy_snacks_prompt(booking: dict, residents: dict) -> str:
    return f"""Generate a Happy Snacks Volunteer Preparation Guide.

## Volunteer Group Info
- Group name: {booking['group_name']}
- Date and time: {booking['start_display']}
- Number of volunteers: {booking['num_volunteers'] or 'Not specified'}
- Duration: {booking['duration_hours']} hours
- Volunteer dietary restrictions: {booking['volunteer_dietary'] or 'None reported'}
- First time at RMH: {'Yes' if booking['first_time'] else 'No'}
- Group notes: {booking['group_notes'] or 'None'}

## Current Resident Families at RMH-OC
- Number of families: {residents.get('num_families', 'Not specified')}
- Total people: {residents.get('total_people', 'Not specified')}
- Children breakdown: {residents.get('children_breakdown') or 'Not specified'}
- Dietary restrictions among residents: {residents.get('dietary_restrictions') or 'None reported'}
- Coordinator notes: {residents.get('volunteer_notes') or 'None'}

---

Generate a warm, practical Happy Snacks Preparation Guide:

# Happy Snacks Preparation Guide
## {booking['group_name']} · {booking['start_display']}

### Who You're Making Snacks For
Describe the families and children warmly. Call out dietary restrictions clearly, especially anything severe.

### Snack Ideas
5–6 specific snack ideas that are:
- Nut-free (all items must be nut-free — state this prominently)
- Fun and appealing for children of different ages
- Individually packaged or portioned so families can take extras to their rooms
- Simple enough for a {booking['duration_hours']}-hour window with {booking['num_volunteers'] or 'your'} volunteers
- Include something for adults too

### Shopping List
Organized shopping list with quantities for {residents.get('total_people', 'the families')} people. Mark RMH pantry staples. Bold any allergy-critical items.

### Logistics
- Arrival and setup
- How snacks are typically distributed at RMH-OC
- What RMH provides
- Time breakdown for the {booking['duration_hours']}-hour shift
- Cleanup

{'### First-Timer Tips' + chr(10) + "Brief tips for a first visit — what to expect, how to connect with families during snack distribution, the emotional side." if booking['first_time'] else ''}

Close warmly from "The RMH-OC Team".
"""


def _build_mcbakers_prompt(booking: dict, residents: dict) -> str:
    return f"""Generate a McBakers Volunteer Preparation Guide.

## Volunteer Group Info
- Group name: {booking['group_name']}
- Date and time: {booking['start_display']}
- Number of volunteers: {booking['num_volunteers'] or 'Not specified'}
- Duration: {booking['duration_hours']} hours
- Volunteer dietary restrictions: {booking['volunteer_dietary'] or 'None reported'}
- First time at RMH: {'Yes' if booking['first_time'] else 'No'}
- Group notes: {booking['group_notes'] or 'None'}

## Current Resident Families at RMH-OC
- Number of families: {residents.get('num_families', 'Not specified')}
- Total people: {residents.get('total_people', 'Not specified')}
- Children breakdown: {residents.get('children_breakdown') or 'Not specified'}
- Dietary restrictions among residents: {residents.get('dietary_restrictions') or 'None reported'}
- Coordinator notes: {residents.get('volunteer_notes') or 'None'}

---

Generate a warm, practical McBakers Preparation Guide:

# McBakers Preparation Guide
## {booking['group_name']} · {booking['start_display']}

### Who You're Baking For
Describe the families warmly. Prominently call out any allergies. Note that baked goods will be individually packaged so families can take them to the hospital or eat later — this is an important design constraint.

### Baked Goods Ideas
4–5 specific baking ideas that are:
- **Individually packaged** (muffins, cookies, bars — not cakes that need to be sliced)
- Nut-free unless resident data says otherwise
- Account for any dietary restrictions among residents
- Realistic to bake in {booking['duration_hours']} hours with {booking['num_volunteers'] or 'your'} volunteers in a home-style kitchen
- Include child-friendly items

For each idea: recipe name, yield, bake time, difficulty, and why families will love it.

### Shopping List
Organized by section. Include quantities. Mark RMH pantry staples (flour, sugar, baking powder, salt, vanilla, butter often available — confirm with coordinator). Bold allergy-critical items.

### Baking Timeline
Detailed time breakdown for a {booking['duration_hours']}-hour shift: setup, bake order (what to start first), cooling time, packaging, cleanup. Be specific — volunteers will use this in the kitchen.

### Packaging & Presentation
Tips on individually packaging baked goods with care — little bags, twine, simple labels, notes from the group. This small touch matters enormously to families.

{'### First-Timer Tips' + chr(10) + "What to expect on a first baking visit, how to connect with any families who wander in, the emotional dimension of the work." if booking['first_time'] else ''}

Close warmly from "The RMH-OC Team".
"""


PROMPT_BUILDERS = {
    "Meal of Love": _build_meal_of_love_prompt,
    "Happy Snacks": _build_happy_snacks_prompt,
    "McBakers": _build_mcbakers_prompt,
}


class GuideGenerator:
    MODEL = "claude-sonnet-4-6"

    def __init__(self, api_key: str | None):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def stream_guide(
        self, booking: dict, residents: dict
    ) -> AsyncGenerator[str, None]:
        service_type = booking.get("service_type", "Meal of Love")
        builder = PROMPT_BUILDERS.get(service_type, _build_meal_of_love_prompt)
        user_prompt = builder(booking, residents)

        async with self.client.messages.stream(
            model=self.MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield f"data: {json.dumps({'type': 'chunk', 'content': text})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"
