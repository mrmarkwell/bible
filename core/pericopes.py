"""Canonical Pericope Service and Knowledge Architecture for Bible Engine.

Zero-dependency implementation (Python 3 standard library only per ADR-003).
Provides:
- Canonical pericope dataset with redemptive-historical headings and summaries.
- Service layer for retrieving pericopes by passage, book, or chapter.
- Idempotent database seeding and verification.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from core.db import Database, PericopeRecord
from core.reference import Book, Reference, get_book, parse_reference

CANONICAL_PERICOPES: List[Tuple[str, str, str]] = [
    (
        "Genesis 1:1 - 2:3",
        "The Creation of the Heavens and the Earth",
        "God speaks the cosmos into existence ex nihilo, culminating in the Sabbath rest pointing to Christ finished work.",
    ),
    (
        "Genesis 2:4-25",
        "The Garden of Eden & The Covenant of Creation",
        "Man placed in God presence as priest-king; the sacred institution of holy marriage.",
    ),
    (
        "Genesis 3:1-24",
        "The Fall and The Protoevangelium",
        "The serpents deception, mans rebellion, and the promise of the Seed of the woman who will crush the serpents head.",
    ),
    (
        "Genesis 4:1-16",
        "Cain and Abel",
        "Acceptable blood sacrifice, the danger of sin crouching at the door, and the split lineages of humanity.",
    ),
    (
        "Genesis 6:9 - 9:17",
        "Noah, the Ark, and the Rainbow Covenant",
        "Universal judgment on human corruption, sovereign preservation through the wooden ark, and common-grace preservation.",
    ),
    (
        "Genesis 11:1-9",
        "The Tower of Babel",
        "Human pride and autonomous rebellion scattered by confusing tongues, anticipating Pentecosts redemptive gathering.",
    ),
    (
        "Genesis 12:1-9",
        "The Call of Abram & Covenant Promise",
        "Unconditional covenant promises of a great nation, promised land, and universal blessing through Abrahams seed.",
    ),
    (
        "Genesis 15:1-21",
        "The Covenant Sealed in Blood",
        "Abram counted righteous by faith alone; Yahweh alone walks between the severed carcasses, swearing sovereign fidelity.",
    ),
    (
        "Genesis 17:1-14",
        "The Sign of Circumcision",
        "The physical seal of the covenant in the flesh, pointing forward to the circumcision of the heart in Christ.",
    ),
    (
        "Genesis 22:1-19",
        "The Binding of Isaac on Mount Moriah",
        "The father offering his beloved only son; Yahweh-Jireh provides the substitute ram, prefiguring the cross of Calvary.",
    ),
    (
        "Genesis 28:10-22",
        "Jacobs Ladder at Bethel",
        "The stairway connecting heaven and earth, fulfilled in Christ the true bridge between God and man.",
    ),
    (
        "Genesis 32:22-32",
        "Jacob Wrestles with God at Peniel",
        "The self-reliant deceiver broken in thigh and spirit, receiving a new name and blessing through clinging faith.",
    ),
    (
        "Genesis 37:1-36",
        "Joseph Sold into Egypt",
        "The beloved son betrayed by his brothers for silver, sent ahead by sovereign providence to preserve life.",
    ),
    (
        "Genesis 50:15-26",
        "Gods Sovereign Providence Over Evil",
        "Joseph reassures his brothers: what man intended for evil, God sovereignly purposed for redemptive salvation.",
    ),
    (
        "Exodus 3:1 - 4:17",
        "The Burning Bush & The Name of I AM",
        "Yahweh reveals His eternal self-existent covenant name to deliver His suffering people from bondage.",
    ),
    (
        "Exodus 12:1-30",
        "The Passover Lamb & The Tenth Plague",
        "The blood of the unblemished lamb shields believers from divine judgment; Christ our Passover sacrificed for us.",
    ),
    (
        "Exodus 14:1-31",
        "The Crossing of the Red Sea",
        "Salvation by sovereign power alone as the waters part; baptism into deliverance while enemies are judged.",
    ),
    (
        "Exodus 19:1 - 20:21",
        "The Giving of the Law at Mount Sinai",
        "The Ten Commandments given in holiness and fire, revealing Gods moral character and exposing human helplessness.",
    ),
    (
        "Exodus 24:1-18",
        "The Covenant Confirmed with Blood",
        "The elders behold the God of Israel upon the sapphire pavement; the blood of the covenant sprinkled.",
    ),
    (
        "Exodus 25:1-9",
        "The Sanctuary and Tabernacle Mandate",
        "The blueprint for God dwelling among His redeemed people, foreshadowing the Incarnation and New Jerusalem.",
    ),
    (
        "Exodus 32:1-35",
        "The Golden Calf & The Mediatorial Breach",
        "Israels swift idolatry breaks the covenant; Moses intercedes on the mountain, offering himself for their sin.",
    ),
    (
        "Exodus 33:12 - 34:9",
        "The Glory of Yahweh Proclaimed",
        "God proclaims His holy character: compassionate, gracious, slow to anger, forgiving iniquity yet by no means clearing the guilty.",
    ),
    (
        "Leviticus 16:1-34",
        "The Day of Atonement (Yom Kippur)",
        "The high priest enters the Holy of Holies with blood; the scapegoat bears away the sins of the congregation.",
    ),
    (
        "Leviticus 17:11",
        "Atonement in the Blood",
        "The life of the flesh is in the blood given upon the altar to make atonement for human souls.",
    ),
    (
        "Numbers 21:4-9",
        "The Bronze Serpent on the Pole",
        "Poisoned rebels look upon the lifted bronze serpent and live, foreshadowing Christ lifted on the cross for sinners.",
    ),
    (
        "Deuteronomy 6:4-9",
        "The Shema & Total Devotion to God",
        "The Lord our God is one Lord; the supreme command to love God with all heart, soul, mind, and strength.",
    ),
    (
        "Deuteronomy 18:15-22",
        "The Prophet Like Moses",
        "Promise of the ultimate Prophet raised from among the brethren, whose words bear absolute divine authority.",
    ),
    (
        "Deuteronomy 30:1-20",
        "Circumcision of the Heart & The Word Near You",
        "The call to repentance; the promise of heart regeneration; Christ the culmination of the law for righteousness.",
    ),
    (
        "Joshua 1:1-9",
        "The Commissioning of Joshua",
        "Be strong and of good courage; meditating on Gods Word day and night guarantees true spiritual success.",
    ),
    (
        "Ruth 4:1-22",
        "The Kinsman-Redeemer & Davids Lineage",
        "Boaz redeems the impoverished Gentile Ruth, grafting her into the covenant royal lineage leading to King Jesus.",
    ),
    (
        "1 Samuel 16:1-13",
        "David Anointed King",
        "Man looks on the outward appearance, but Yahweh looks on the heart; David anointed with the Holy Spirit.",
    ),
    (
        "1 Samuel 17:1-58",
        "David and Goliath: The Champion of Israel",
        "The anointed substitute champion defeats the enemy for his helpless people, securing victory by faith alone.",
    ),
    (
        "2 Samuel 7:1-17",
        "The Davidic Covenant",
        "God promises David an everlasting kingdom, an enduring throne, and a royal Son who will reign forever.",
    ),
    (
        "1 Kings 8:1-66",
        "Solomon Dedicates the Temple",
        "The glory of the Lord fills the house; Solomons intercession for forgiveness, foreigners, and covenant mercy.",
    ),
    (
        "Job 19:23-27",
        "I Know that My Redeemer Lives",
        "Amidst intense suffering and loss, Job confesses unwavering faith in a living Redeemer and bodily resurrection.",
    ),
    (
        "Psalm 1:1-6",
        "The Two Ways: The Blessed Tree and Chaff",
        "The blessed righteous man delights in Yahwehs law, while the ungodly are like chaff blown away in judgment.",
    ),
    (
        "Psalm 2:1-12",
        "The Reign of the Lords Anointed King",
        "The nations rage in vain; God installs His Son on Zion; kiss the Son, lest He be angry and you perish.",
    ),
    (
        "Psalm 16:1-11",
        "The Golden Psalm of Hope & Resurrection",
        "You will not abandon my soul to Sheol, nor let your Holy One see corruption; fullness of joy in Gods presence.",
    ),
    (
        "Psalm 22:1-31",
        "The Suffering and Exaltation of the Messiah",
        "The pierced hands and feet, mockery, and forsakenness of the cross, turning into global praise and kingdom dominion.",
    ),
    (
        "Psalm 23:1-6",
        "The Lord is My Shepherd",
        "Covenant peace and security through dark valleys, feasting in the presence of foes, dwelling in Yahwehs house forever.",
    ),
    (
        "Psalm 51:1-19",
        "A Broken and Contrite Heart: Davids Repentance",
        "Confession of inherent sinfulness, plea for cleansing with hyssop, and prayer for a clean heart and renewed spirit.",
    ),
    (
        "Psalm 103:1-22",
        "Bless the Lord, O My Soul: Abundant Mercy",
        "Yahweh forgives all iniquities, heals diseases, and removes transgressions as far as the east is from the west.",
    ),
    (
        "Psalm 110:1-7",
        "The Priest-King in the Order of Melchizedek",
        "The Lord says to my Lord: Sit at my right hand; eternal royal priesthood and crushing defeat of hostile kings.",
    ),
    (
        "Proverbs 3:1-8",
        "Trust in the Lord with All Your Heart",
        "Lean not on your own understanding; acknowledge God in all your ways and He will make your paths straight.",
    ),
    (
        "Isaiah 6:1-13",
        "The Vision of the Thrice-Holy God & Isaiahs Commission",
        "Holy, holy, holy is the Lord of hosts; burning coal purges unclean lips; Here am I! Send me.",
    ),
    (
        "Isaiah 7:10-17",
        "The Sign of Immanuel",
        "The virgin shall conceive and bear a son, and shall call His name Immanuel (God with us).",
    ),
    (
        "Isaiah 9:1-7",
        "Unto Us a Child is Born: The Prince of Peace",
        "Light dawns upon Galilee of the Gentiles; the government shall be upon His shoulder; of His peace there is no end.",
    ),
    (
        "Isaiah 11:1-10",
        "The Righteous Branch from Jesses Stump",
        "The Spirit of the Lord rests upon the Messiah with wisdom, understanding, and righteousness, renewing all creation.",
    ),
    (
        "Isaiah 40:1-31",
        "Comfort My People & The Transcendent Creator",
        "A voice crying in the wilderness: prepare the way of the Lord; the grass withers, but Gods Word stands forever.",
    ),
    (
        "Isaiah 52:13 - 53:12",
        "The Fourth Servant Song: The Pierced Substitute",
        "He was pierced for our transgressions, crushed for our iniquities; upon Him was the chastisement that brought us peace.",
    ),
    (
        "Isaiah 55:1-13",
        "An Invitation to the Thirsty & The Everlasting Covenant",
        "Come, everyone who thirsts, buy wine and milk without money; Gods thoughts are higher than our thoughts.",
    ),
    (
        "Isaiah 65:17-25",
        "The New Heavens and New Earth",
        "Behold, I create new heavens and a new earth; former troubles forgotten; wolves and lambs feeding together.",
    ),
    (
        "Jeremiah 31:31-34",
        "The Promise of the New Covenant",
        "Not like the broken covenant from Egypt; God writes His law on their hearts, forgives iniquity, and remembers sin no more.",
    ),
    (
        "Ezekiel 36:22-38",
        "A New Heart and The Indwelling Spirit",
        "God sprinkles clean water, removes the heart of stone, gives a heart of flesh, and puts His Spirit within them.",
    ),
    (
        "Ezekiel 37:1-14",
        "The Valley of Dry Bones: Sovereign Regeneration",
        "Can these dry bones live? The prophetic word and breath of the Spirit bring dead bones to life as a mighty army.",
    ),
    (
        "Daniel 7:9-14",
        "The Ancient of Days & The Son of Man",
        "Thrones placed and judgment sits; one like a Son of Man arrives on the clouds of heaven, receiving an everlasting dominion.",
    ),
    (
        "Micah 5:2-5",
        "The Ruler from Bethlehem Ephrathah",
        "Out of small Bethlehem comes the eternal Ruler whose goings forth have been from of old, from everlasting.",
    ),
    (
        "Habakkuk 2:1-4",
        "The Righteous Shall Live by Faith",
        "The proud soul is puffed up and not upright, but the righteous person lives by his steadfast faith in God.",
    ),
    (
        "Matthew 1:18-25",
        "The Incarnation: You Shall Call His Name Jesus",
        "Conceived by the Holy Spirit, Jesus is born to save His people from their sins, fulfilling the prophecy of Immanuel.",
    ),
    (
        "Matthew 3:13-17",
        "The Baptism of Jesus & Trinitarian Revelation",
        "Jesus fulfills all righteousness; the Spirit descends like a dove; the Father proclaims: This is my beloved Son.",
    ),
    (
        "Matthew 4:1-11",
        "The Temptation in the Wilderness",
        "The Second Adam overcomes the devil where Israel and Adam failed, wielding the sword of the written Word of God.",
    ),
    (
        "Matthew 5:1-12",
        "The Beatitudes: Character of the Kingdom",
        "Blessed are the poor in spirit, the meek, the peacemakers, and those persecuted for righteousness sake.",
    ),
    (
        "Matthew 5:17-20",
        "Christ Fulfills the Law and the Prophets",
        "Not a jot or tittle will pass from the law; Christ does not abolish the law but fulfills every demand in perfect obedience.",
    ),
    (
        "Matthew 6:9-13",
        "The Lords Prayer (The Disciples Prayer)",
        "Our Father in heaven, hallowed be your name; your kingdom come; give us this day our daily bread; forgive our debts.",
    ),
    (
        "Matthew 16:13-20",
        "Peters Confession & The Church on the Rock",
        "You are the Christ, the Son of the living God; on this rock of apostolic confession Christ builds His invincible church.",
    ),
    (
        "Matthew 26:26-30",
        "The Institution of the Lords Supper",
        "Take, eat; this is my body... this is my blood of the new covenant, poured out for many for the remission of sins.",
    ),
    (
        "Matthew 27:32-56",
        "The Crucifixion and Death of Jesus",
        "Darkness over the land; the temple veil torn from top to bottom; the earth shakes; the Roman centurion confesses Christ.",
    ),
    (
        "Matthew 28:16-20",
        "The Great Commission & Sovereign Authority",
        "All authority in heaven and on earth has been given to me; go therefore and make disciples of all nations.",
    ),
    (
        "Mark 1:14-15",
        "The Gospel of God: Repent and Believe",
        "The time is fulfilled and the kingdom of God is at hand; repent and believe in the good news of Jesus Christ.",
    ),
    (
        "Mark 10:41-45",
        "The Son of Man Came to Serve and Give a Ransom",
        "Greatness in the kingdom found in servanthood; Christ gives His life as a substitutionary ransom for many.",
    ),
    (
        "Luke 1:46-55",
        "Marys Song of Praise (The Magnificat)",
        "My soul magnifies the Lord; God scatters the proud and exalts the humble, remembering His mercy to Abraham.",
    ),
    (
        "Luke 2:1-20",
        "The Nativity of Jesus Christ & Angels Song",
        "Glory to God in the highest, and on earth peace among men with whom He is pleased; good news of great joy for all people.",
    ),
    (
        "Luke 15:11-32",
        "The Parable of the Prodigal Son & The Loving Father",
        "The rebellious son welcomed home with open arms, a royal robe, and a feast, contrasting with the moralistic older brother.",
    ),
    (
        "Luke 24:13-35",
        "The Road to Emmaus: Christ in All the Scriptures",
        "Beginning with Moses and all the Prophets, the risen Christ interprets to them in all the Scriptures the things concerning Himself.",
    ),
    (
        "John 1:1-18",
        "The Word Became Flesh: The Cosmic Prologue",
        "In the beginning was the Word, and the Word was with God, and the Word was God; the Word became flesh and dwelt among us.",
    ),
    (
        "John 3:1-21",
        "You Must Be Born Again & The Love of God",
        "Unless one is born from above he cannot see the kingdom; as Moses lifted the serpent, so must the Son of Man be lifted up.",
    ),
    (
        "John 4:1-26",
        "The Samaritan Woman at the Well: Living Water",
        "Whoever drinks of the water that Christ gives will never thirst; true worshipers worship the Father in spirit and truth.",
    ),
    (
        "John 6:25-59",
        "I Am the Bread of Life from Heaven",
        "True manna from heaven that gives eternal life; whoever feeds on this bread will live forever.",
    ),
    (
        "John 10:1-18",
        "The Good Shepherd Lays Down His Life for the Sheep",
        "The thief comes only to steal and kill, but Christ comes that they may have life abundantly; no one takes His life from Him.",
    ),
    (
        "John 11:17-44",
        "I Am the Resurrection and the Life",
        "Jesus weeps over death; cries Lazarus, come out!; demonstrates supreme sovereign power over physical and spiritual death.",
    ),
    (
        "John 14:1-14",
        "I Am the Way, the Truth, and the Life",
        "No one comes to the Father except through Christ; believing in Jesus is seeing the Father.",
    ),
    (
        "John 15:1-17",
        "I Am the True Vine: Abiding in Christ",
        "Apart from Christ you can do nothing; abiding in His love produces lasting spiritual fruit and joy.",
    ),
    (
        "John 17:1-26",
        "The High Priestly Prayer",
        "Jesus prays for His own glory, the preservation and sanctification of His disciples, and the eternal unity of all believers.",
    ),
    (
        "John 19:17-30",
        "The Crucifixion: It is Finished (Tetelestai)",
        "The full penalty of sin paid in full; Christ bows His head and yields up His spirit in sovereign victory.",
    ),
    (
        "John 20:1-18",
        "The Empty Tomb and Resurrection of Jesus",
        "The stone rolled away; the graveclothes lying neat; the risen Lord appears to Mary Magdalene in the garden.",
    ),
    (
        "Acts 2:1-41",
        "The Outpouring of the Holy Spirit at Pentecost",
        "Tongues like fire, sound of a rushing wind; Peter preaches Christ crucified and risen; three thousand souls saved.",
    ),
    (
        "Acts 7:1-60",
        "Stephens Apostolic Defense & Martyrdom",
        "Tracing redemptive history from Abraham to Solomon; Stephen beholds the Son of Man standing at Gods right hand.",
    ),
    (
        "Acts 9:1-19",
        "The Conversion of Saul on the Damascus Road",
        "The fierce persecutor arrested by blinding heavenly light; Saul, Saul, why do you persecute me?",
    ),
    (
        "Acts 15:1-35",
        "The Jerusalem Council: Saved by Grace Alone",
        "Gentiles are saved through the grace of the Lord Jesus just as the Jews, without circumcision or ceremonial bondage.",
    ),
    (
        "Romans 1:16-17",
        "The Power of God for Salvation",
        "I am not ashamed of the gospel; the righteousness of God revealed from faith to faith; the righteous shall live by faith.",
    ),
    (
        "Romans 3:21-26",
        "Righteousness Through Faith: Justification by Grace",
        "All have sinned and fall short of the glory of God, and are justified by His grace as a gift through the redemption in Christ.",
    ),
    (
        "Romans 5:1-11",
        "Peace with God & Reconciliation Through Christ",
        "Justified by faith, we have peace with God; God demonstrates His love for us in that while we were still sinners, Christ died for us.",
    ),
    (
        "Romans 5:12-21",
        "The Two Federal Heads: Adam and Christ",
        "Sin and condemnation entered through one man (Adam); grace and life reign through the one Man Jesus Christ.",
    ),
    (
        "Romans 8:1-11",
        "Life in the Spirit: No Condemnation",
        "There is now no condemnation for those in Christ Jesus; the law of the Spirit of life sets believers free from sin and death.",
    ),
    (
        "Romans 8:12-17",
        "Heirs with Christ & The Spirit of Adoption",
        "Led by the Spirit of God; receiving the Spirit of adoption by whom we cry Abba! Father!; fellow heirs with Christ.",
    ),
    (
        "Romans 8:18-30",
        "Future Glory & The Golden Chain of Redemption",
        "Creation groans awaiting redemption; God works all things together for good; foreknown, predestined, called, justified, glorified.",
    ),
    (
        "Romans 8:31-39",
        "Everlasting Covenant Love: More Than Conquerors",
        "If God is for us, who can be against us? Nothing can separate us from the love of God in Christ Jesus our Lord.",
    ),
    (
        "Romans 9:1-29",
        "Gods Sovereign Election and Mercy",
        "Gods purpose according to election stands, not of works but of Him who calls; I will have mercy on whom I have mercy.",
    ),
    (
        "Romans 11:33-36",
        "The Great Doxology of Sovereign Wisdom",
        "Oh, the depth of the riches and wisdom and knowledge of God! For from Him and through Him and to Him are all things.",
    ),
    (
        "Romans 12:1-2",
        "Living Sacrifices & Renewed Minds",
        "Present your bodies as a living sacrifice, holy and acceptable to God; do not be conformed, but be transformed by the renewing of your mind.",
    ),
    (
        "1 Corinthians 1:18-25",
        "The Word of the Cross: Wisdom and Power of God",
        "The word of the cross is folly to those who are perishing, but to us who are being saved it is the power of God.",
    ),
    (
        "1 Corinthians 13:1-13",
        "The Way of Love: Patient, Kind, Never Failing",
        "Without love, tongues and knowledge are empty noise; love never ends; faith, hope, and love abide, but the greatest is love.",
    ),
    (
        "1 Corinthians 15:1-11",
        "The Gospel of First Importance",
        "Christ died for our sins in accordance with the Scriptures, was buried, and was raised on the third day in accordance with the Scriptures.",
    ),
    (
        "1 Corinthians 15:12-28",
        "The Resurrection of Christ: Firstfruits of Life",
        "If Christ has not been raised, our preaching is vain and your faith futile; but in fact Christ has been raised, the firstfruits.",
    ),
    (
        "1 Corinthians 15:50-58",
        "Mystery Revealed: Death Swallowed Up in Victory",
        "We shall all be changed, in a moment, in the twinkling of an eye; O death, where is your victory? Thanks be to God!",
    ),
    (
        "2 Corinthians 5:16-21",
        "The Ministry of Reconciliation & New Creation",
        "If anyone is in Christ, he is a new creation; God made Him who knew no sin to be sin for us, that we might become the righteousness of God in Him.",
    ),
    (
        "2 Corinthians 12:1-10",
        "Thorn in the Flesh: My Grace is Sufficient",
        "Pauls thorn prevents boasting; the Lord answers: My grace is sufficient for you, for my power is made perfect in weakness.",
    ),
    (
        "Galatians 2:15-21",
        "Justification by Faith: Crucified with Christ",
        "A person is not justified by works of the law but through faith in Jesus Christ; I have been crucified with Christ; it is no longer I who live.",
    ),
    (
        "Galatians 3:10-14",
        "Christ Redeemed Us from the Curse of the Law",
        "Christ redeemed us from the curse of the law by becoming a curse for us, so that the blessing of Abraham might come to the Gentiles.",
    ),
    (
        "Galatians 5:16-26",
        "The Fruit of the Spirit vs. Works of the Flesh",
        "Walk by the Spirit, and you will not gratify the desires of the flesh; the fruit of the Spirit is love, joy, peace, patience, kindness, goodness, faithfulness.",
    ),
    (
        "Ephesians 1:3-14",
        "Spiritual Blessings in Heavenly Places",
        "Blessed be the God and Father who chose us in Christ before the foundation of the world, predestined us for adoption, and sealed us with the Spirit.",
    ),
    (
        "Ephesians 2:1-10",
        "By Grace Through Faith: Gods Masterpiece",
        "Dead in trespasses, but God made us alive together with Christ; by grace you have been saved through faith; created for good works.",
    ),
    (
        "Ephesians 2:11-22",
        "One New Man in Christ: The Dividing Wall Broken",
        "Christ has broken down the dividing wall of hostility between Jew and Gentile, reconciling both to God in one body through the cross.",
    ),
    (
        "Ephesians 6:10-20",
        "The Whole Armor of God",
        "Stand firm against the schemes of the devil, taking up the shield of faith, helmet of salvation, and sword of the Spirit.",
    ),
    (
        "Philippians 2:5-11",
        "The Christ Hymn: Kenosis and Exaltation",
        "Though in the form of God, He emptied Himself, taking the form of a servant; therefore God has highly exalted Him above every name.",
    ),
    (
        "Philippians 3:7-14",
        "The Surpassing Worth of Knowing Christ Jesus",
        "Counting all things as loss for the sake of knowing Christ; found in Him, not having a righteousness of my own, but that through faith.",
    ),
    (
        "Colossians 1:15-20",
        "The Supremacy of Christ in Creation and Redemption",
        "He is the image of the invisible God, the firstborn of all creation; in Him all things hold together; head of the body, the church.",
    ),
    (
        "Colossians 2:13-15",
        "Alive in Christ: The Record of Debt Canceled",
        "God made us alive together with Him, having canceled the record of debt that stood against us, nailing it to the cross.",
    ),
    (
        "1 Thessalonians 4:13-18",
        "The Comfort of the Lords Glorious Return",
        "The Lord Himself will descend from heaven with a cry of command; the dead in Christ will rise first; comfort one another with these words.",
    ),
    (
        "2 Timothy 3:14-17",
        "All Scripture is Breathed Out by God (Theopneustos)",
        "All Scripture is inspired by God and profitable for teaching, for reproof, for correction, and for training in righteousness.",
    ),
    (
        "Hebrews 1:1-4",
        "God Has Spoken by His Son: The Ultimate Revelation",
        "Long ago God spoke by the prophets, but in these last days He has spoken to us by His Son, the radiance of the glory of God.",
    ),
    (
        "Hebrews 4:14-16",
        "Our Great High Priest & The Throne of Grace",
        "We have a high priest who is able to sympathize with our weaknesses; let us then with confidence draw near to the throne of grace.",
    ),
    (
        "Hebrews 7:23-28",
        "The Eternal and Sinless Priesthood of Jesus",
        "He holds His priesthood permanently because He lives forever; able to save to the uttermost those who draw near to God through Him.",
    ),
    (
        "Hebrews 8:1-13",
        "The Mediator of a Better Covenant",
        "Christ serves in the true tent pitched by the Lord; mediator of a covenant enacted on better promises.",
    ),
    (
        "Hebrews 9:11-28",
        "Redemption Through the Blood of Christ",
        "Christ entered once for all into the holy places by means of His own blood, securing an eternal redemption.",
    ),
    (
        "Hebrews 10:1-18",
        "Christs Sacrifice Once for All",
        "By a single offering He has perfected for all time those who are being sanctified; where there is forgiveness, there is no longer any offering for sin.",
    ),
    (
        "Hebrews 11:1-40",
        "The Hall of Faith: Assurance of Things Hoped For",
        "Faith is the assurance of things hoped for, the conviction of things not seen; by faith Abel, Enoch, Noah, Abraham, and Moses persevered.",
    ),
    (
        "Hebrews 12:1-3",
        "Looking to Jesus: The Founder and Perfecter of Faith",
        "Surrounded by so great a cloud of witnesses, let us run with endurance, looking to Jesus who for the joy set before Him endured the cross.",
    ),
    (
        "James 1:19-27",
        "Doers of the Word, Not Hearers Only",
        "Quick to hear, slow to speak, slow to anger; be doers of the word and not hearers only, deceiving yourselves.",
    ),
    (
        "James 2:14-26",
        "Faith Without Works is Dead",
        "Faith by itself, if it does not have works, is dead; true saving faith inevitably demonstrates itself in loving, active obedience.",
    ),
    (
        "1 Peter 1:3-9",
        "A Living Hope Born Through the Resurrection",
        "Born again to a living hope through the resurrection of Jesus Christ from the dead, to an inheritance that is imperishable and unfading.",
    ),
    (
        "1 Peter 2:4-10",
        "A Chosen Race, A Royal Priesthood",
        "You are a chosen race, a royal priesthood, a holy nation, that you may proclaim the excellencies of Him who called you out of darkness.",
    ),
    (
        "1 Peter 2:21-25",
        "He Bore Our Sins in His Body on the Tree",
        "He committed no sin; when reviled, He did not revile in return; by His wounds you have been healed.",
    ),
    (
        "1 John 1:5 - 2:2",
        "Walking in the Light & Christ Our Advocate",
        "God is light, and in Him is no darkness at all; if we confess our sins, He is faithful and just; Christ is the propitiation for our sins.",
    ),
    (
        "1 John 4:7-21",
        "God is Love: Love Perfected in Us",
        "Beloved, let us love one another, for love is from God; in this the love of God was made manifest: God sent His only Son that we might live through Him.",
    ),
    (
        "Jude 24-25",
        "The Great Apostolic Doxology",
        "Now to Him who is able to keep you from stumbling and to present you blameless before the presence of His glory with great joy, be glory forever.",
    ),
    (
        "Revelation 1:9-20",
        "The Vision of the Glorified Son of Man",
        "One like a son of man amidst seven golden lampstands; His face shining like the sun; Fear not, I am the first and the last, and the living one.",
    ),
    (
        "Revelation 4:1-11",
        "The Heavenly Throne Room: Holy, Holy, Holy",
        "A throne in heaven with an emerald rainbow; twenty-four elders; four living creatures crying Holy, holy, holy is the Lord God Almighty.",
    ),
    (
        "Revelation 5:1-14",
        "The Lion and the Lamb Opening the Scroll",
        "Weep no more! The Lion of Judah has conquered; a Lamb standing as though slain takes the scroll; Worthy is the Lamb who was slain!",
    ),
    (
        "Revelation 7:9-17",
        "The Great Multitude from Every Nation",
        "A great multitude that no one could number from every nation, clothed in white robes, waving palm branches: Salvation belongs to our God!",
    ),
    (
        "Revelation 19:11-16",
        "The Rider on the White Horse: King of Kings",
        "Heaven opened and a white horse appeared; its rider is called Faithful and True; on His robe is written: King of Kings and Lord of Lords.",
    ),
    (
        "Revelation 21:1-8",
        "The New Heaven, New Earth, and New Jerusalem",
        "Behold, the dwelling place of God is with man; He will wipe away every tear; death shall be no more; Behold, I am making all things new.",
    ),
    (
        "Revelation 22:1-7",
        "The River of the Water of Life & The Tree of Life",
        "A river of the water of life flowing from the throne; the tree of life bearing twelve kinds of fruit; no longer will there be anything accursed.",
    ),
    (
        "Revelation 22:12-21",
        "Come, Lord Jesus: The Final Promise and Benediction",
        "Behold, I am coming soon... I am the Alpha and the Omega, the first and the last; the Spirit and the Bride say, Come! Amen. Come, Lord Jesus!",
    ),
]


class PericopeService:
    """Service layer managing scripture pericope sections and redemptive summaries."""

    def __init__(self, db: Database) -> None:
        """Initialize PericopeService with Database connection."""
        self.db = db

    def add_pericope(
        self,
        reference: Union[Reference, str],
        title: str,
        redemptive_summary: Optional[str] = None,
        genre: Optional[str] = None,
        literary_structure: Optional[str] = None,
        central_proposition: Optional[str] = None,
    ) -> PericopeRecord:
        """Insert a single pericope section into the database."""
        return self.db.insert_pericope(
            reference,
            title,
            redemptive_summary=redemptive_summary,
            genre=genre,
            literary_structure=literary_structure,
            central_proposition=central_proposition,
        )

    def get_pericopes_for_passage(
        self,
        reference: Union[Reference, str],
    ) -> List[PericopeRecord]:
        """Fetch all pericope headings overlapping with the specified passage citation."""
        return self.db.get_pericopes_for_reference(reference)

    def get_pericopes_for_book(
        self,
        book: Union[Book, str, int],
        chapter: Optional[int] = None,
    ) -> List[PericopeRecord]:
        """Retrieve all pericope headings for an entire book or a specific chapter."""
        return self.db.get_pericopes_for_book(book, chapter=chapter)

    def count_pericopes(self, book_id: Optional[int] = None) -> int:
        """Count total pericopes stored in the database."""
        return self.db.count_pericopes(book_id=book_id)

    def seed_canonical_pericopes(self) -> int:
        """Seed predefined canonical pericope headings into the database.

        Checks existing pericopes to avoid duplicating titles for the same citation.
        Returns the number of pericopes inserted.
        """
        cur = self.db.conn.cursor()
        cur.execute("SELECT human_ref, title FROM pericopes")
        existing = {(r[0].lower().strip(), r[1].lower().strip()) for r in cur.fetchall()}
        cur.close()

        to_insert: List[Tuple[Union[Reference, str], str, Optional[str]]] = []
        for ref_str, title, summary in CANONICAL_PERICOPES:
            key = (ref_str.lower().strip(), title.lower().strip())
            try:
                parsed_ref = parse_reference(ref_str)
                key = (parsed_ref.format().lower().strip(), title.lower().strip())
            except Exception:
                pass

            if key not in existing:
                to_insert.append((ref_str, title, summary))

        if to_insert:
            return self.db.insert_pericopes_batch(to_insert)
        return 0
