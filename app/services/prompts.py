import json
from collections.abc import Iterable

from pydantic import BaseModel

from app.models import AdCopy, CreativeInput, Hook, MessagingAngle, Platform, VisualConcept, VisualConceptDraft

PLATFORM_COPY_LIMITS: dict[Platform, dict[str, int]] = {
    Platform.META: {"primary_text": 125, "headline": 40, "description": 30},
    Platform.GOOGLE: {"primary_text": 90, "headline": 30, "description": 90},
    Platform.TIKTOK: {"primary_text": 100, "headline": 40, "description": 80},
}

PLATFORM_ASPECT_RATIOS: dict[Platform, list[str]] = {
    Platform.META: ["1:1", "4:5", "9:16"],
    Platform.GOOGLE: ["1:1", "16:9", "1.91:1"],
    Platform.TIKTOK: ["9:16"],
}

CREATIVE_SYSTEM_PROMPT = (
    "You are Creative Director Engine, a senior direct-response creative strategist and ad production planner. "
    "Return only valid JSON matching the requested schema. "
    "Every output must be specific to the product, use case, audience, and platform. "
    "Avoid cinematic fluff, generic startup language, empty hype, vague visuals, and unsupported claims. "
    "Think like a paid-media operator building ads that ship this week."
)


def brand_context(payload: CreativeInput) -> str:
    brand_colors = ", ".join(payload.brand_colors) if payload.brand_colors else "Not specified"
    logo_hint = "Logo is provided and must be used" if payload.logo_image else "Not provided"
    return (
        f"Brand: {payload.brand_name}\n"
        f"Product: {payload.product_description}\n"
        f"Audience: {payload.target_audience}\n"
        f"Platform: {payload.platform.value}\n"
        f"Objective: {payload.objective.value}\n"
        f"Tone: {payload.tone}\n"
        f"Key benefits: {', '.join(payload.key_benefits)}\n"
        f"Competitors: {', '.join(payload.competitors) if payload.competitors else 'None listed'}\n"
        f"Visual style: {payload.visual_style or 'Not specified'}\n"
        f"Brand colors (must prioritize): {brand_colors}\n"
        f"Logo reference: {logo_hint}"
    )


def serialize_models(items: Iterable[object]) -> str:
    serialized_items = [
        item.model_dump(mode="json") if isinstance(item, BaseModel) else item
        for item in items
    ]
    return json.dumps(
        serialized_items,
        separators=(",", ":"),
    )


def serialize_selected(items: Iterable[BaseModel], fields: list[str]) -> str:
    selected = [{field: getattr(item, field) for field in fields} for item in items]
    return json.dumps(selected, separators=(",", ":"))


def hook_prompt(payload: CreativeInput) -> str:
    required_types = ["curiosity", "fear_based", "benefit_driven", "contrarian", "social_proof"]
    return (
        "Task: Generate high-converting paid-media hooks.\n\n"
        f"{brand_context(payload)}\n\n"
        f"Return JSON with a top-level `hooks` array containing exactly {payload.hook_count} objects.\n"
        "Each object must contain: `type`, `text`, `rationale`.\n"
        f"Allowed `type` values only: {', '.join(required_types)}.\n"
        "Distribution rules:\n"
        "- Cover all five hook types at least once before repeating any type.\n"
        "- Vary mechanism, emotional trigger, and sentence structure.\n"
        "- Make the product and user outcome obvious in the hook itself.\n"
        "- No duplicate ideas with different wording.\n"
        "- No generic curiosity-only hooks.\n"
        "- No brand manifesto language.\n"
        "Write hooks as deployable ad openers, not brainstorm fragments."
    )


def angle_prompt(payload: CreativeInput) -> str:
    return (
        "Task: Generate platform-aware messaging angles for this campaign.\n\n"
        f"{brand_context(payload)}\n\n"
        f"Return JSON with a top-level `angles` array containing exactly {payload.angle_count} objects.\n"
        "Each object must contain: `name`, `description`, `target_emotion`, `use_case`.\n"
        "Angle rules:\n"
        "- Each angle must be materially different in sales argument, not just tone.\n"
        "- Anchor each angle in a concrete buyer problem, desired outcome, or proof mechanism.\n"
        "- Prefer direct-response utility over abstract storytelling.\n"
        "- Avoid repeating the same benefit in five ways.\n"
        "- Angle names must be short, specific, and execution-ready (2-4 words)."
    )


def ad_copy_prompt(payload: CreativeInput, hooks: list[Hook], angles: list[MessagingAngle]) -> str:
    return (
        "You are an expert performance marketing copywriter specializing in high-converting ads for Meta, Instagram, and Google.\n"
        "Your task is to generate ultra-concise, high-impact ad copy that maximizes scroll-stopping power and click-through rate (CTR).\n\n"
        f"{brand_context(payload)}\n\n"
        "Use these hooks:\n"
        f"{serialize_selected(hooks[: min(len(hooks), payload.copy_count)], ['type', 'text'])}\n\n"
        "Use these messaging angles:\n"
        f"{serialize_selected(angles, ['name', 'description', 'target_emotion'])}\n\n"
        f"Return JSON with a top-level `ad_copies` array containing exactly {payload.copy_count} objects.\n"
        "STRICT RULES (MUST FOLLOW):\n\n"
        "1. PRIMARY TEXT:\n"
        "- Max 12 words\n"
        "- Only ONE sentence\n"
        "- Must be either: (a) A punchy emotional statement OR (b) A curiosity-driven hook\n"
        "- Do NOT explain the product or use filler words\n"
        "- Must feel premium, sharp, and instantly engaging\n\n"
        "2. HEADLINE:\n"
        "- Max 7 words\n"
        "- Must be a complete phrase, never clipped\n"
        "- Focus on clear benefit, aspiration, or transformation\n"
        "- Strong, bold, and direct\n"
        "- No punctuation unless absolutely necessary\n\n"
        "3. DESCRIPTION:\n"
        "- Max 5 words, minimum 5 characters (or return empty string)\n"
        "- Add ONLY if it strengthens clarity or urgency, otherwise return an empty string\n"
        "- Must be complete phrase if provided (not abbreviations or single words)\n\n"
        "4. VARIATIONS & STYLE:\n"
        "- Rotate between these 3 styles: Emotional Hook, Curiosity Hook, Minimalist Premium\n"
        "- Avoid generic phrases like 'high quality', 'best product', 'crafted for you'\n"
        "- Prefer emotional triggers: confidence, status, transformation, desire, curiosity\n\n"
        "5. COMPLETENESS RULE (CRITICAL):\n"
        "- Never end headline with a dangling number/token (bad: 'Food in 10').\n"
        "- If a number implies time, include the unit (good: 'Food in 10 Minutes').\n"
        "- CTA must be an actual action phrase, 2-4 words (examples: 'Order Now', 'Get Started', 'Learn More').\n\n"
        "OUTPUT FORMAT (STRICT JSON):\n"
        "Each object must include: `hook_text`, `angle_name`, `primary_text`, `headline`, `cta`, and `description`."
    )


def visual_concept_prompt(
    payload: CreativeInput,
    hooks: list[Hook],
    angles: list[MessagingAngle],
    ad_copies: list[AdCopy] | None = None,
) -> str:
    aspect_ratios = ", ".join(PLATFORM_ASPECT_RATIOS[payload.platform])
    copy_context = ""
    if ad_copies:
        copy_context = (
            "Candidate hook-angle-copy combinations. Select the strongest combinations for the visuals, "
            "prioritizing clear buyer desire, product relevance, and CTA alignment:\n"
            f"{serialize_selected(ad_copies[: min(len(ad_copies), payload.concept_count * 2)], ['hook_text', 'angle_name', 'primary_text', 'headline', 'cta', 'description'])}\n\n"
        )
    return (
        "Task: Generate visual ad concepts that can be handed to an image generation model.\n\n"
        f"{brand_context(payload)}\n\n"
        "Reference hooks:\n"
        f"{serialize_selected(hooks[: min(len(hooks), payload.concept_count)], ['text'])}\n\n"
        "Reference angles:\n"
        f"{serialize_selected(angles, ['name', 'description'])}\n\n"
        f"{copy_context}"
        f"Return JSON with a top-level `visual_concepts` array containing exactly {payload.concept_count} objects.\n"
        f"Prefer these aspect ratios for {payload.platform.value}: {aspect_ratios}.\n"
        "Each concept must contain: `hook_text`, `angle_name`, `scene_description`, `camera_angle`, "
        "`background_setting`, `color_palette`, `mood`, `style_reference`, `aspect_ratio`, `media_type`.\n"
        "Brand consistency rules:\n"
        "- If brand colors are provided, color_palette must use those exact hex values as the primary palette.\n"
        "- Do not introduce unrelated dominant colors when brand colors are provided.\n"
        "- If logo reference is provided, compose negative space and focal hierarchy suitable for logo presence.\n"
        "- If reference images are provided, borrow composition language, iconography style, and color blocking from them.\n"
        "- Keep brand identity cues from reference images while generating a fresh ad, not a direct copy.\n"
        "\nCRITICAL - ZERO META-COMPOSITION RULE:\n"
        "DO NOT mention: laptops, monitors, screens, tablets, phones, people, hands, users, viewers, audience.\n"
        "ONLY describe: the product/interface/outcome directly.\n\n"
        "Product-Focused Examples (FOLLOW THESE PATTERNS):\n"
        "✓ GOOD: 'Clean dashboard with blue metrics, orange buttons, real-time charts'\n"
        "✓ GOOD: 'Modern app interface showing task lists, calendar, notifications'\n"
        "✓ GOOD: 'Product packaging on neutral background with premium lighting'\n"
        "✓ GOOD: 'Before/after split: chaotic workspace → organized workflow'\n"
        "✓ GOOD: 'Abstract representation of interconnected data flows and efficiency'\n"
        "✗ BAD: 'Person using a laptop showing the dashboard'\n"
        "✗ BAD: 'Screen displaying product on a desk'\n"
        "✗ BAD: 'Someone looking at the app'\n"
        "✗ BAD: 'Hand holding a phone with app open'\n\n"
        "Scene guidelines:\n"
        "- For SaaS/software: describe the UI/interface directly with specific colors, elements, layout\n"
        "- For physical products: describe the product with materials, finish, lighting, context\n"
        "- For services: describe the outcome/benefit directly\n"
        "- Use Apple product photography as reference: premium, minimal, hero-focused\n"
        "- Include lighting direction, background style, color palette, and visual hierarchy\n"
        "- The concept should fill the entire ad frame - no extra space or 'device showing ad' metaphors"
    )


def nanobanana_prompt(
    payload: CreativeInput,
    concept: VisualConceptDraft | VisualConcept,
    ad_copy: AdCopy | None = None,
) -> str:
    benefit_line = ", ".join(payload.key_benefits[:3])
    copy_direction = ""
    if ad_copy:
        copy_direction = (
            f"Selected hook: {ad_copy.hook_text}. Selected angle: {ad_copy.angle_name}. "
            "The final image must already contain these exact readable text elements as part of the design: "
            f"headline text \"{ad_copy.headline}\"; bodyline text \"{ad_copy.primary_text}\"; "
            f"CTA button text \"{ad_copy.cta}\". "
            "Use clean commercial typography, strong contrast, correct spelling, and a clear CTA button. "
        )
    return (
        f"Create a {concept.aspect_ratio} {concept.media_type.value} performance ad creative for {payload.brand_name}. "
        f"Scene: {concept.scene_description}. Camera angle: {concept.camera_angle}. "
        f"Background: {concept.background_setting}. Mood: {concept.mood}. "
        f"Style: {concept.style_reference}. Palette: {', '.join(concept.color_palette)}. "
        f"Audience: {payload.target_audience}. Objective: {payload.objective.value}. "
        f"{copy_direction}"
        f"Core benefit cues: {benefit_line}. Platform-native look for {payload.platform.value}. "
        "Keep the product large, readable, and grounded in realistic usage. "
        "Commercially realistic, product-led, high-contrast, no watermarks, no floating UI, no abstract movie-poster composition. "
        "Generate the complete finished ad image with the visual, headline, bodyline, and CTA button already present in the image."
    )


def premium_nanobanana_prompt(
    payload: CreativeInput,
    concept: VisualConceptDraft | VisualConcept,
    ad_copy: AdCopy | None = None,
) -> str:
    headline = (ad_copy.headline if ad_copy else "Work Faster")[:40]
    body = (ad_copy.primary_text if ad_copy else "Built for modern teams")[:80]
    cta = (ad_copy.cta if ad_copy else "Start Free")[:18]
    hook_text = " ".join((ad_copy.hook_text if ad_copy else "").split())
    hook_words = len(hook_text.split()) if hook_text else 0
    include_hook_in_image = 0 < hook_words <= 6
    hook_line = f'HOOK TEXT: "{hook_text}"\n' if include_hook_in_image else ""
    hook_positioning = "- hook text above headline" if include_hook_in_image else "- no hook text inside image"
    brand_palette = ", ".join(payload.brand_colors) if payload.brand_colors else ", ".join(concept.color_palette)
    logo_rule = (
        "Include the provided logo as a clean brand mark; keep proportions intact and placement natural."
        if payload.logo_image
        else "No external logo reference provided."
    )
    reference_balance_rule = (
        "Reference guidance: use the uploaded sample image as a composition/style anchor. "
        f"Requested similarity strength: {payload.reference_similarity:.2f} on a 0.00-1.00 scale "
        "(0.00 = loose inspiration, 1.00 = very close style/layout). "
        "Preserve reference composition according to this strength, while keeping generated output original and brand-safe. "
        "Do not copy pixel-for-pixel; keep it recognizably inspired but fresh."
        if payload.sample_images
        else "No sample reference image was provided."
    )

    return f"""
Create a premium high-converting commercial advertisement for {payload.brand_name}.

STYLE:
Modern Meta/Facebook/Instagram sponsored ad.
Premium startup aesthetic.
Apple-level product composition.
Clean luxury commercial design.

PRODUCT:
{concept.scene_description}

BACKGROUND:
{concept.background_setting}

MOOD:
{concept.mood}

CAMERA:
{concept.camera_angle}

VISUAL STYLE:
{concept.style_reference}

ASPECT RATIO:
{concept.aspect_ratio}

COLOR PALETTE:
{brand_palette}

TARGET AUDIENCE:
{payload.target_audience}

OBJECTIVE:
{payload.objective.value}

COMPOSITION RULES:
- Product/interface is the main hero
- Product occupies 60-70% of frame
- Strong visual hierarchy
- Clean negative spacing
- Balanced modern layout
- Premium studio lighting
- Soft shadows
- High contrast
- Realistic reflections
- Sharp focus
- Commercial product photography
- Conversion-focused composition
- Strictly follow the provided brand colors as dominant tones

TEXT LAYOUT:
Render these exact text elements clearly and correctly.
{hook_line}HEADLINE: "{headline}"
BODY TEXT: "{body}"
CTA BUTTON: "{cta}"

Typography requirements:
- modern sans-serif font
- bold clean headline
- perfect spelling
- highly readable
- premium ad typography
- strong contrast
- realistic CTA button
- natural text placement
- no distorted letters
- no fake paragraphs

Text positioning:
- headline near top-left
- body text below headline
- CTA button near bottom-center
{hook_positioning}

IMPORTANT:
Do NOT generate:
- laptops
- monitors
- people
- hands
- office desks
- nested screens
- screenshots
- fake UI text
- random letters
- clutter
- watermarks

{logo_rule}
{reference_balance_rule}
The advertisement itself fills the entire frame.
The final result should look like a real Instagram sponsored ad and production-ready commercial creative.
"""


def huggingface_prompt(
    payload: CreativeInput,
    concept: VisualConceptDraft | VisualConcept,
    ad_copy: AdCopy | None = None,
) -> str:
    """
    Optimized premium ad-generation prompt.
    Designed for Imagen / FLUX / SDXL style models.
    Focuses on:
    - clean ad composition
    - readable short typography
    - premium commercial aesthetics
    - avoiding nested screen hallucinations
    """

    benefit_line = ", ".join(payload.key_benefits[:3])

    headline = ad_copy.headline if ad_copy else "Work Faster"
    primary_text = ad_copy.primary_text if ad_copy else "Built for modern teams"
    cta = ad_copy.cta if ad_copy else "Start Free"

    # Keep text SHORT for better typography rendering
    headline = headline[:40]
    primary_text = primary_text[:60]
    cta = cta[:18]

    brand_palette_line = ", ".join(payload.brand_colors) if payload.brand_colors else ", ".join(concept.color_palette)
    logo_rule = (
        "Use the provided logo reference as brand identity anchor; preserve logo proportions and avoid distortion."
        if payload.logo_image
        else "No external logo reference provided."
    )

    return (f"""
Create a premium commercial advertisement for {payload.brand_name}.

IMPORTANT:
This is a COMPLETE standalone advertisement design.
Do NOT generate:
- laptops
- monitors
- desks
- people using devices
- screenshots inside screens
- nested advertisements
- hands holding phones
- office scenes
- meta-compositions

The advertisement itself fills the entire frame.

════════════════════════════
CORE VISUAL
════════════════════════════

Main concept:
{concept.scene_description}

Camera angle:
{concept.camera_angle}

Background:
{concept.background_setting}

Mood:
{concept.mood}

Style:
{concept.style_reference}

Color palette:
{brand_palette_line}

Platform:
{payload.platform.value}

Aspect ratio:
{concept.aspect_ratio}

════════════════════════════
VISUAL STYLE
════════════════════════════

Generate a modern high-end advertising creative.

Style references:
- Apple advertising
- Stripe landing pages
- Airbnb campaigns
- premium SaaS branding
- Instagram sponsored creatives
- venture-backed startup aesthetics

The composition must feel:
- premium
- clean
- modern
- commercial
- balanced
- conversion-focused

Use:
- strong visual hierarchy
- elegant spacing
- realistic lighting
- soft shadows
- subtle gradients
- premium UI styling
- minimal clutter
- high contrast
- modern layout design
- strict adherence to provided brand color hex values

════════════════════════════
PRODUCT RULES
════════════════════════════

The product or interface must:
- occupy most of the frame
- be the clear hero element
- be large and visually dominant
- be professionally lit
- look realistic and premium
- remain crystal clear
- avoid distortion

For SaaS or apps:
- show elegant dashboard/UI directly
- UI fills the composition naturally
- avoid showing the UI inside devices

════════════════════════════
TEXT RENDERING
════════════════════════════

Render ONLY these exact text elements:

HEADLINE:
"{headline}"

BODY TEXT:
"{primary_text}"

CTA BUTTON:
"{cta}"

Typography requirements:
- modern sans-serif typography
- clean kerning
- highly readable
- short text only
- correctly spelled
- bold headline
- premium commercial design
- strong contrast
- realistic button design

Layout:
- headline near top
- body text near center
- CTA button near bottom

IMPORTANT:
Keep text minimal and perfectly readable.
Do NOT generate extra paragraphs.
Do NOT generate fake UI text.
Do NOT generate random letters.
{logo_rule}

════════════════════════════
NEGATIVE PROMPT
════════════════════════════

Avoid:
- blurry text
- unreadable typography
- distorted letters
- duplicated elements
- fake paragraphs
- random UI text
- clutter
- low quality
- messy composition
- floating objects
- watermark
- people
- laptops
- office desks
- nested screens
- screenshots
- bad spacing
- overcomplicated layouts

════════════════════════════
FINAL QUALITY TARGET
════════════════════════════

The final result should look like:
- a real Instagram ad
- premium Meta advertisement
- App Store feature banner
- startup launch campaign
- commercial SaaS creative
- professionally designed marketing visual

Commercial-ready.
Premium.
Modern.
High-converting.
"""
    )


def scoring_prompt(
    payload: CreativeInput,
    concept: VisualConcept,
    copy: dict[str, str],
) -> str:
    return (
        "Task: Evaluate one finished ad concept for direct-response quality.\n\n"
        f"{brand_context(payload)}\n\n"
        f"Visual concept: {json.dumps(concept.model_dump(mode='json'), separators=(',', ':'))}\n"
        f"Copy payload: {json.dumps(copy, separators=(',', ':'))}\n\n"
        "Return only JSON with keys: `clarity`, `persuasion`, `cta_alignment`, `platform_fit`, `rationale`.\n"
        "Scoring rubric:\n"
        "- clarity: Is the message instantly understandable?\n"
        "- persuasion: Does it create desire, urgency, or credibility?\n"
        "- cta_alignment: Does the CTA match the promise and objective?\n"
        "- platform_fit: Does it feel native to the platform and constraints?\n"
        "Use 0-100 integers. Be strict. Penalize generic copy, mismatched CTA, unclear value prop, or abstract visuals."
    )
