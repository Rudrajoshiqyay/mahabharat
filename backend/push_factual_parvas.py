import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USERNAME")
PWD = os.getenv("NEO4J_PASSWORD")
db_driver = GraphDatabase.driver(URI, auth=(USER, PWD))

factual_summaries = {
    "Anukramanika Parva": {
        "events": "Sauti (Ugrasrava) arrives at the Naimisha forest where the great sages, led by Saunaka, are holding a 12-year sacrifice. Sauti introduces himself and recites the index and overarching summary of the Mahabharata, establishing the framing narrative of the epic.",
        "next": "This sets the stage for a more detailed outline of the 18 major books of the Mahabharata in the next Parva."
    },
    "Sangraha Parva": {
        "events": "Sauti provides a high-level outline and categorization of all 18 major Parvas (books) of the Mahabharata. He lists the contents, major events, and the number of chapters and slokas in each book.",
        "next": "With the structure of the epic outlined, the story moves into the mythological background of King Janamejaya's ancestors and the sages."
    },
    "Paushya Parva": {
        "events": "Contains the foundational story of King Janamejaya's curse by the dog Sarama, and the stories of the sage Dhaumya and his devoted disciples (Upamanyu, Aruni, and Veda). It heavily features Utanka's quest to retrieve magical earrings from King Paushya, which leads to his conflict with the snake king Takshaka.",
        "next": "Utanka's anger towards Takshaka leads him to convince King Janamejaya to wage a genocidal war against all snakes (the snake sacrifice), driving the plot forward."
    },
    "Pauloma Parva": {
        "events": "Focuses on the history of the Bhargava race. It details the story of the great sage Bhrigu, the birth of Chyavana, and the love story of Ruru and Pramadvara (where Ruru gives half his life to resurrect his poisoned bride).",
        "next": "These stories of curses and snakes bridge the narrative toward the great snake sacrifice of Janamejaya."
    },
    "Astika Parva": {
        "events": "Details the mythological Churning of the Ocean (Samudra Manthan) and the rivalry between Kadru and Vinata. It tells the epic story of Garuda stealing the nectar of immortality (Amrita) to free his mother. It culminates in King Janamejaya's terrifying snake sacrifice, which is ultimately stopped by the young sage Astika.",
        "next": "With the snake sacrifice halted, Janamejaya asks to hear the full history of his ancestors (the Kuru dynasty), beginning the actual core story of the Mahabharata."
    },
    "Adivansavatarana Parva": {
        "events": "Provides the detailed genealogy of the gods, demons, and the Lunar Dynasty (which includes the Kuru lineage). It explains how the gods and demons incarnated on Earth as the various kings and warriors of the Mahabharata.",
        "next": "Having traced the cosmic origins, the epic prepares to introduce the direct earthly ancestors of the Pandavas and Kauravas."
    },
    "Sambhava Parva": {
        "events": "A massive and crucial Parva that details the birth and early lives of the central characters. It includes the famous story of King Dushyanta and Shakuntala (parents of Emperor Bharata), the story of King Yayati, and finally the birth, education, and early rivalries of the Pandavas and Kauravas.",
        "next": "The intense jealousy of the Kauravas towards the young Pandavas escalates into assassination plots in the next Parva."
    },
    "Jatugriha Parva": {
        "events": "Duryodhana and Shakuni plot to assassinate the Pandavas and their mother Kunti by building a highly flammable palace made of lac (the Lakshagriha) in Varanavata. Warned by Vidura, the Pandavas dig a secret tunnel, set the house on fire themselves, and escape into the forest.",
        "next": "Believed to be dead by the world, the Pandavas must now survive incognito in the dangerous wilderness."
    },
    "Hidimva-vadha Parva": {
        "events": "While wandering the forest, the Pandavas are attacked by the man-eating Rakshasa, Hidimba. Bhima slays Hidimba in a brutal wrestling match and subsequently marries his sister, Hidimbi. Together, they have a powerful magical son named Ghatotkacha.",
        "next": "The Pandavas continue their disguised wandering and seek refuge in a quiet village."
    },
    "Vaka-vadha Parva": {
        "events": "The Pandavas live disguised as Brahmins in the town of Ekachakra. They discover the town is being terrorized by a demon named Bakasura, who demands human sacrifices. Kunti orders Bhima to protect their hosts, and Bhima brutally kills Bakasura.",
        "next": "News of a grand Swayamvara (marriage contest) reaches the Pandavas, drawing them out of hiding."
    },
    "Chaitraratha Parva": {
        "events": "On their way to Panchala, the Pandavas encounter and defeat the Gandharva king Angaraparna. In friendship, the Gandharva tells them the ancestral stories of Tapati and the legendary rivalry between the sages Vasishtha and Vishwamitra. He advises them to appoint a priest.",
        "next": "With Dhaumya appointed as their royal priest, the Pandavas finally arrive at the Swayamvara."
    },
    "Swayamvara Parva": {
        "events": "King Drupada of Panchala hosts an archery contest for the hand of his daughter, Draupadi. While all the great kings (including Karna and Duryodhana) fail, Arjuna, still disguised as a poor Brahmin, strings the legendary bow and hits the target, winning Draupadi.",
        "next": "The dramatic victory of a supposed Brahmin angers the kings, leading to a massive brawl and the revelation of the Pandavas' true identities."
    },
    "Vaivahika Parva": {
        "events": "The Pandavas reveal their true royal identities to King Drupada. Due to a misunderstanding by Kunti ('share whatever you have brought equally'), it is decided that Draupadi will marry all five Pandava brothers. Sage Vyasa arrives to explain the divine justification for this polyandrous marriage.",
        "next": "News that the Pandavas are alive and allied with the powerful King Drupada reaches Hastinapura, forcing the Kauravas to react."
    },
    "Viduragamana Parva": {
        "events": "King Dhritarashtra, advised by Bhishma and Drona, sends the wise Vidura to Panchala with gifts to officially invite the Pandavas and their new bride back to Hastinapura in peace.",
        "next": "The Pandavas return home, but the underlying tensions remain, forcing a political compromise."
    },
    "Rajya-labha Parva": {
        "events": "To avoid a civil war, Dhritarashtra divides the kingdom in half. He gives the Kauravas the wealthy capital of Hastinapura and gives the Pandavas the barren wasteland of Khandavaprastha. Through hard work and divine help, the Pandavas transform the wasteland into the magnificent city of Indraprastha.",
        "next": "The Pandavas establish their rule, but a rule regarding Draupadi's privacy leads to a sudden complication for Arjuna."
    },
    "Arjuna-vanavasa Parva": {
        "events": "Arjuna accidentally walks in on Yudhishthira and Draupadi in their private chambers while retrieving his weapons to help a Brahmin. To honor their strict marriage pact, Arjuna voluntarily goes into a 12-year exile. During his travels, he marries the Naga princess Ulupi and the princess of Manipur, Chitrangada.",
        "next": "Arjuna's travels eventually bring him to the city of Dwarka, where he meets his greatest ally, Krishna."
    },
    "Subhadra-harana Parva": {
        "events": "In Dwarka, Arjuna falls deeply in love with Krishna's half-sister, Subhadra. With Krishna's secret encouragement and plotting, Arjuna dramatically abducts Subhadra on a chariot right in front of the Vrishni warriors.",
        "next": "The angered Vrishnis are calmed by Krishna, and they accept the marriage, cementing the alliance between the Pandavas and Krishna's clan."
    },
    "Haranaharana Parva": {
        "events": "Arjuna returns to Indraprastha with Subhadra. Krishna and the Vrishnis follow, bringing immense wealth and dowry. Subhadra gives birth to the legendary warrior Abhimanyu, and Draupadi gives birth to five sons (the Upapandavas).",
        "next": "The Pandava kingdom flourishes in peace and power, setting up the final cosmic event of the Adi Parva."
    },
    "Khandava-daha Parva": {
        "events": "The fire god Agni asks Krishna and Arjuna to help him consume the Khandava forest to cure his illness. Equipped with new divine weapons (the Gandiva bow and the Sudarshana Chakra), Arjuna and Krishna burn the forest, defeating the god Indra and slaughtering the fleeing creatures. They save Maya Danava, an architect demon.",
        "next": "In gratitude for his life, Maya Danava promises to build an illusionary, magnificent assembly hall for the Pandavas, which triggers the events of Book 2."
    }
}

def push_factual_summaries():
    for parva_title, data in factual_summaries.items():
        summary_text = f"WHAT HAPPENS IN THIS PARVA:\\n{data['events']}\\n\\nCONTEXT FOR THE NEXT PARVA:\\n{data['next']}"
        with db_driver.session() as session:
            session.run("MATCH (p:Parva {title: $title}) SET p.summary = $summary", title=parva_title, summary=summary_text)
        print(f"Pushed factual summary for {parva_title}")

if __name__ == "__main__":
    push_factual_summaries()
    db_driver.close()
