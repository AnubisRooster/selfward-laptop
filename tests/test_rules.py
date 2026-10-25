import unittest
from sf import rules as r, graph

class Feelings(unittest.TestCase):
    def test_many_wordings_become_one_label(self):
        for text, want in (("I was scared and afraid", ["Fear"]), ("so stressed lately", ["Stress"]), ("I'm furious, really annoyed", ["Anger"]), ("feeling tearful and miserable", ["Sadness"]),
                           ("I feel exhausted and burnt out", ["Exhaustion"]), ("She was proud and I felt relieved", ["Relief", "Pride"]), ("I'm so grateful today", ["Gratitude"]), ("I was embarrassed", ["Embarrassment"])):
            self.assertEqual(sorted(r.feelings_in(text)), sorted(want), text)
    def test_old_labels_are_unchanged_so_earlier_maps_still_line_up(self):
        self.assertEqual(sorted(r.feelings_in("angry sad anxious fearful guilty ashamed lonely frustrated jealous overwhelmed hopeless helpless worthless numb empty betrayed confused hurt grief happy hopeful")),
                         sorted(["Anger", "Sadness", "Anxiety", "Fear", "Guilt", "Shame", "Loneliness", "Frustration", "Jealousy", "Overwhelmed", "Hopeless", "Helpless", "Worthless", "Numb", "Empty", "Betrayed", "Confused", "Hurt", "Grief", "Happy", "Hopeful"]))
    def test_denying_a_feeling_is_not_having_it(self):
        for text in ("I am not anxious today", "I'm never really sad", "I don't feel scared", "I wasn't angry", "without any shame"): self.assertEqual(r.feelings_in(text), [], text)
        self.assertEqual(r.feelings_in("I can't stop being anxious"), ["Anxiety"]); self.assertEqual(r.feelings_in("not a good day, I felt sad"), ["Sadness"])
    def test_whole_words_only_and_ambiguous_words_stay_out(self):
        for text in ("a painting of a sadder day", "the content of the file", "I live on my own street", "flat tire, strong coffee, a pet peeve", "too much coffee", "I lost my keys", "I hope you are well"): self.assertEqual(r.feelings_in(text), [], text)

class People(unittest.TestCase):
    def test_relations_with_or_without_an_adjective(self):
        self.assertEqual(sorted(r.people_in("My older sister called, my best friend moved, my new boss, and my girlfriend")), ["Boss", "Friend", "Girlfriend", "Sister"])
        self.assertEqual(sorted(r.people_in("my manager, my coworkers, my mom and my stepdad, my kids, my grandma")), ["Boss", "Child", "Colleague", "Father", "Grandparent", "Mother"])
    def test_ex_partners_are_one_person_not_also_a_wife_or_husband(self):
        self.assertEqual(r.people_in("my ex-wife and my ex"), ["Ex-partner"]); self.assertEqual(r.people_in("my former husband"), ["Ex-partner"]); self.assertEqual(r.people_in("my wife and my ex-husband"), ["Ex-partner", "Wife"])
    def test_a_relation_has_to_be_mine_and_whole(self):
        for text in ("my moment of clarity", "my example", "my pet peeve", "the boss said", "your mother", "my sonata", "my catalog"): self.assertEqual(r.people_in(text), [], text)
        self.assertEqual(r.people_in("my dogs"), ["Pet"])

class Beliefs(unittest.TestCase):
    def test_one_clause_per_opener_and_generic_openers_are_not_beliefs(self):
        self.assertEqual(r.beliefs_in("I always fail when it matters. I feel calm now, though."), ["i always fail when it matters"])
        self.assertEqual(r.beliefs_in("I'm not anxious today"), []); self.assertEqual(r.beliefs_in("nobody will notice, I'm too tired"), [])
        self.assertIn("it's my fault that she left", r.beliefs_in("It's my fault that she left, I think."))
        self.assertTrue(all(len(b) <= 70 for b in r.beliefs_in("I think that " + "very " * 40 + "long")))
    def test_an_opener_followed_by_more_words_is_not_cut_in_the_middle(self):
        self.assertEqual(r.beliefs_in("I feel like I'm not good enough for this job"), ["i'm not good enough for this job"])

class Events(unittest.TestCase):
    def test_life_events(self):
        self.assertEqual(sorted(r.events_in("I got laid off, the deadline moved, and then the funeral")), ["Deadline", "Funeral", "Layoff", "Moved"])
        self.assertEqual(sorted(r.events_in("I was diagnosed in the hospital after the accident")), ["Accident", "Diagnosis", "Hospital"])
    def test_everyday_words_that_only_look_like_events(self):
        for text in ("wake up and go to the row of shops", "raise my voice", "I'm sick of it", "speech recognition", "a normal operation of the machine"): self.assertEqual(r.events_in(text), [], text)

class Dreams(unittest.TestCase):
    def test_the_many_ways_of_telling_one(self):
        for text in ("I had a dream last night", "I had a weird dream about my dad", "I keep having the same nightmare", "I dreamt of the ocean", "I dreamed that I could fly", "I was dreaming about school",
                     "in my dream there was a door", "I woke up from a terrible dream", "this recurring dream again", "a dream where I fall", "Last night I had a really vivid and strange dream"): self.assertTrue(r.looks_like_a_dream(text), text)
    def test_hopes_and_figures_of_speech_are_not_dreams(self):
        for text in ("my dream job would be nice", "I dream of being a writer", "I would never dream of it", "dream big", "my dream home", "I want to live my dream life"): self.assertFalse(r.looks_like_a_dream(text), text)

class OnTheMap(unittest.TestCase):
    def test_a_natural_message_now_lands_on_the_map(self):
        nodes, edges = graph.analyze("My manager Dana keeps moving the deadline and I'm so stressed and scared. I always fail when it matters.")
        self.assertEqual(sorted(n for n in nodes), sorted([("emotion", "Stress"), ("emotion", "Fear"), ("person", "Boss"), ("event", "Deadline"), ("event", "Moved"), ("belief", "i always fail when it matters")]))
        self.assertIn(("Boss", "Stress", "TRIGGERS"), edges); self.assertIn(("Stress", "Fear", "ASSOCIATED_WITH"), edges); self.assertIn(("Fear", "i always fail when it matters", "CAUSES"), edges)

if __name__ == "__main__": unittest.main()
