"""The skill descriptions decide which skill Claude picks, so their routing phrases are pinned here."""
import re
import unittest

from ofa import ROOT

# Skill listing cap for description plus when_to_use, from the Claude Code skills reference.
LISTING_CAP = 1536


def description(skill):
    text = (ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    return re.search(r"^description: (.*)$", text, re.M).group(1)


class SkillDescriptionTest(unittest.TestCase):
    def test_fit_the_listing_cap(self):
        for skill in ("odoo-functional", "odoo-explain"):
            with self.subTest(skill=skill):
                self.assertLessEqual(len(description(skill)), LISTING_CAP)

    def test_functional_claims_proposals_in_both_languages(self):
        text = description("odoo-functional")
        for phrase in ("proposal request or RFP", "propose the best way", "propón la mejor forma",
                       "standard, configuration or development", "`Target: <name>`"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_explain_hands_proposals_to_functional(self):
        text = description("odoo-explain")
        for phrase in ("proposal or RFP", "`Target: <name>`", "go to odoo-functional"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
