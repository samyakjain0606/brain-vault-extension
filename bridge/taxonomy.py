"""
The shelves, topics and tags Brain Vault sorts into.

The descriptions are sent to Jev as the meaning of each option, so keep them
concrete and mutually exclusive. Edit freely to fit your own vault.
"""

# Shelf = what kind of thing it is (drives how the site shows it).
SHELVES = {
    "reading": {
        "name": "Reading",
        "jev": "Something to read: an essay, blog post, article, newsletter, paper, documentation page, or a long-form article published on X.",
    },
    "post": {
        "name": "Posts",
        "jev": "A short social post, such as a single tweet or a thread on X, where the post itself is the thing being saved.",
    },
    "inspiration": {
        "name": "Inspiration",
        "jev": "An app, website, product page or visual design saved as a reference for how it looks or works, to learn from or copy ideas.",
    },
    "tool": {
        "name": "Tools",
        "jev": "A tool, library, service, code repository, plugin or resource collection saved to use later, such as an icon library or a developer tool.",
    },
}

# Topic = what it is about. One per item, so they must not overlap.
TOPICS = {
    "ai": {
        "name": "AI and agents",
        "jev": "Artificial intelligence: language models, AI agents, prompting, AI coding tools, machine learning research.",
    },
    "engineering": {
        "name": "Software engineering",
        "jev": "Building software without an AI focus: programming, architecture, developer tools, open source, infrastructure.",
    },
    "design": {
        "name": "Design",
        "jev": "Visual and product design: UI and UX, typography, icons, illustration, animation, design systems, design resources.",
    },
    "startups": {
        "name": "Startups and product",
        "jev": "Starting and growing companies: founders, startup ideas, product strategy, brand, marketing, growth.",
    },
    "craft": {
        "name": "Work and craft",
        "jev": "How to do good work: productivity, learning, careers, habits, taste, doing great work.",
    },
    "writing": {
        "name": "Writing and content",
        "jev": "Writing and making content: writing style, copywriting, storytelling, social media content.",
    },
    "money": {
        "name": "Money and markets",
        "jev": "Personal finance, investing, stock markets, economics and business models.",
    },
    "other": {
        "name": "Other",
        "jev": "None of the other topics fits well.",
    },
}

# Tags = finer detail. Jev answers yes/no for each, and code keeps the confident ones.
TAGS = {
    "onboarding": "About onboarding flows or first-run experiences in an app.",
    "empty states": "About empty states, blank screens or zero-data design.",
    "landing page": "About how to design landing pages, or a collection of landing page examples. A product's own homepage does not count.",
    "mobile app": "Specifically about phone apps or mobile screen design, such as a gallery of iOS or Android app screens.",
    "typography": "About fonts, type choices or typographic layout.",
    "icons": "Provides or discusses icons or icon sets.",
    "illustration": "Provides or discusses illustrations or vector graphics such as SVGs.",
    "animation": "About motion design, animation or animated assets.",
    "design system": "About design systems, component libraries or UI kits.",
    "ui patterns": "A library or gallery of real app screens or UI patterns to browse for reference.",
    "prompting": "About writing prompts or getting better output from AI models.",
    "ai agents": "About AI agents, agent tooling or agentic workflows.",
    "coding tools": "About tools or editors that help write code, including AI coding assistants.",
    "claude": "Specifically about Anthropic's Claude or Claude Code.",
    "open source": "An open source project or repository.",
    "essay": "A reflective essay making an argument, like a Paul Graham essay.",
    "productivity": "About productivity, focus or working effectively.",
    "learning": "About learning, skill growth or getting better at something.",
    "founders": "About founders, starting a company or startup advice.",
    "ideas": "About how to come up with ideas or be creative, as the subject itself. Galleries of design inspiration do not count.",
    "branding": "About brand, positioning or how products are perceived.",
    "writing style": "About writing style or improving how you write.",
    "careers": "About careers, jobs or professional growth.",
}
