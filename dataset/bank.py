"""Data banks: names, places, domains (25), personas.  Pure data, no logic beyond tiny parsers."""
from __future__ import annotations

from dataclasses import dataclass, field

FIRST = ("Ana Ben Carla Dmitri Elif Farah Gabriel Hana Ivan Jun Katya Liam Mia Nadia Omar Priya Quinn Rosa Sven Tara "
         "Umar Vera Wen Xavier Yara Zoe Aiden Bruno Chloe Dev Elena Felix Greta Hugo Isla Jamal Kofi Lena Mateo Noor "
         "Olga Pedro Rin Sofia Tomas Uma Viktor Wanjiru Yusuf Zainab").split()
LAST = ("Silva Okafor Novak Tanaka Haddad Lindqvist Moreau Petrov Reyes Kowalski Nguyen Fischer Costa Rossi Singh "
        "Almeida Bergstrom Castillo Dubois Eriksson Ferreira Garcia Hoang Ibrahim Jensen Kim Larsen Mendes Nakamura "
        "Oliveira Park Quispe Rahman Sato Torres Ueda Vasquez Weber Yilmaz").split()
CITIES = ("Lisbon Porto Madrid Barcelona Paris Lyon Berlin Munich Rome Milan Vienna Prague Warsaw Oslo Stockholm Dublin "
          "Amsterdam Brussels Zurich Athens Istanbul Cairo Nairobi Lagos Cape Town Dubai Mumbai Delhi Bangkok Singapore "
          "Tokyo Osaka Seoul Sydney Auckland Toronto Chicago Austin Denver Seattle Boston Miami Lima Bogota Santiago "
          "Buenos Aires").replace("Cape Town", "Cape_Town").replace("Buenos Aires", "Buenos_Aires").split()
CITIES = [c.replace("_", " ") for c in CITIES]
COMPANIES = ("Acme Northwind Globex Initech Umbrella Hooli Vandelay Stark Wayne Soylent Cyberdyne Tyrell Gringotts "
             "Oscorp Aperture Wonka Pied_Piper Massive_Dynamic Bluth Dunder_Mifflin").replace("_", " ").split(" ")
COMPANIES = ["Acme", "Northwind", "Globex", "Initech", "Hooli", "Vandelay", "Stark Works", "Soylent", "Tyrell",
             "Aperture", "Wonka Foods", "Bluth Homes", "Pied Piper", "Gringotts", "Oscorp", "Lumen Labs", "Orbit Freight",
             "Fernhill", "Quartz Bank", "Maple & Oak"]

MONTHS = {
    "en": "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(),
    "es": "ene feb mar abr may jun jul ago sep oct nov dic".split(),
    "fr": "janv févr mars avr mai juin juil août sept oct nov déc".split(),
    "de": "Jan Feb Mär Apr Mai Jun Jul Aug Sep Okt Nov Dez".split(),
    "pt": "jan fev mar abr mai jun jul ago set out nov dez".split(),
    "it": "gen feb mar apr mag giu lug ago set ott nov dic".split(),
}
WEEKDAYS = {
    "en": "Mon Tue Wed Thu Fri Sat Sun".split(),
    "es": "lun mar mié jue vie sáb dom".split(),
    "fr": "lun mar mer jeu ven sam dim".split(),
    "de": "Mo Di Mi Do Fr Sa So".split(),
    "pt": "seg ter qua qui sex sáb dom".split(),
    "it": "lun mar mer gio ven sab dom".split(),
}
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]
LANGS = ["es", "fr", "de", "pt", "it"]

# ----------------------------------------------------------------------------------------------
# Domains.  Mini-languages:
#   metrics:  "Label:fmt:lo:hi:dec:goodDirection" separated by "|"   (fmt: see kit.FMT)
#   sets:     name -> comma list
#   tables:   "Title|Col=kind:args;Col=kind:args"  (kinds: id:PFX, pick:a,b, num:lo,hi,dec, item, person, date, city, money)
#   entity:   "Title|Key=kind:args;..."
# ----------------------------------------------------------------------------------------------

@dataclass
class Domain:
    key: str
    title: str
    personas: list[str]
    metrics: list[str]
    sets: dict[str, str]
    tables: list[str]
    entity: str
    tasks: list[str] = field(default_factory=list)   # work sequences for plan/timeline
    heldout: bool = False


def _d(key, title, personas, metrics, sets, tables, entity, tasks, heldout=False) -> Domain:
    return Domain(key, title, personas, metrics.split("|"), {k: v for k, v in sets.items()}, tables, entity,
                  tasks.split("|"), heldout)


DOMAINS: list[Domain] = [
    _d("saas", "SaaS analytics",
       ["You are the analytics copilot for a SaaS team.", "You are Beacon, the product-analytics assistant inside Lumen Metrics. Be brief."],
       "MRR:usd_k:20:90:1:up|Churn rate:pct:0.8:4.5:1:down|New customers:count:80:420:0:up|Trial conversion:pct:8:32:1:up|Weekly active users:count:900:12000:0:up|NPS:score:20:72:0:up|Support tickets:count:60:640:0:down",
       {"channel": "Organic,Paid search,Referral,Partners,Email,Social", "plan": "Free,Starter,Pro,Team,Enterprise", "region": "North America,EMEA,APAC,LATAM"},
       ["Accounts|Account=item;Plan=pick:Starter,Pro,Team,Enterprise;Seats=num:3,400,0;MRR=money:200,9000;Owner=person",
        "Feature requests|ID=id:FR;Request=pick:SSO for Team plan,Dark mode,CSV export,Audit log,Webhooks v2,Usage alerts;Votes=num:4,180,0;Status=pick:Planned,Open,Shipped"],
       "Account|Plan=pick:Starter,Pro,Team,Enterprise;Seats=num:3,400,0;Renewal=date;Owner=person;Health=pick:Healthy,At risk,Expanding",
       "Audit the tracking plan|Backfill last quarter's events|Rebuild the retention cohort|Publish the dashboard|Review with the growth lead"),
    _d("ecom", "online store operations",
       ["You are the merchandising assistant for Fernhill, an online home-goods store.", "You are Cart, an ops assistant for a Shopify-style store. Keep it short."],
       "Revenue:usd_k:12:95:1:up|Orders:count:240:3100:0:up|Average order value:usd:34:140:0:up|Conversion rate:pct:1.2:4.8:1:up|Return rate:pct:2:11:1:down|Cart abandonment:pct:55:82:0:down",
       {"category": "Lighting,Textiles,Kitchen,Storage,Decor,Outdoor", "channel": "Direct,Search,Instagram,Email,Marketplace", "warehouse": "Porto,Rotterdam,Leipzig,Katowice"},
       ["Top products|Product=pick:Linen throw,Oak shelf,Brass desk lamp,Ceramic planter,Wool rug,Glass carafe,Cotton duvet;Units=num:40,1800,0;Revenue=money:900,48000;Stock=num:0,600,0",
        "Open orders|Order=id:ORD;Customer=person;Total=money:20,480;Status=pick:Packed,Shipped,Delayed,Pending payment"],
       "Product|SKU=id:SKU;Price=money:12,240;Stock=num:0,500,0;Supplier=pick:Nordhaus,Kiln & Co,Brightloom,Terra Goods;Rating=num:3,5,1",
       "Pull the supplier invoices|Reconcile stock counts|Update the product feed|Launch the weekend promo|Review returns"),
    _d("devops", "engineering operations",
       ["You are the on-call copilot for the platform team.", "You are Pager, an SRE assistant embedded in the incident channel. No fluff."],
       "Uptime:pct:98.5:99.99:2:up|p95 latency:ms:80:900:0:down|Error rate:pct:0.01:2.5:2:down|Deploys:count:4:60:0:up|MTTR:min:8:180:0:down|Open incidents:count:0:14:0:down",
       {"service": "api-gateway,billing,search,auth,notifications,checkout", "env": "prod,staging,canary,dev", "team": "Platform,Payments,Growth,Data,Mobile"},
       ["Open incidents|ID=id:INC;Title=pick:Checkout timeouts,Login loop on SSO,Stale search index,Webhook retries piling up,Disk pressure on db-3,Elevated 5xx on api;Severity=pick:SEV1,SEV2,SEV3;Owner=person",
        "Deployments|Service=pick:api-gateway,billing,search,auth,notifications,checkout;Version=id:v2.;Status=pick:Succeeded,Rolled back,In progress;Duration=num:2,31,0"],
       "Service|Owner=pick:Platform,Payments,Growth,Data;Language=pick:Go,Python,TypeScript,Rust;On-call=person;Last deploy=date;SLO=pick:99.9%,99.95%,99.99%",
       "Reproduce the failure in staging|Bisect the last three deploys|Ship the fix behind a flag|Run the load test|Write the postmortem"),
    _d("fintech", "personal finance",
       ["You are the money assistant inside Quartz Bank's mobile app.", "You are Penny, a budgeting assistant. Be calm and precise."],
       "Monthly spend:usd:900:6200:0:down|Savings rate:pct:3:38:0:up|Balance:usd:800:24000:0:up|Dining out:usd:60:620:0:down|Subscriptions:usd:30:260:0:down|Investments:usd_k:2:90:1:up",
       {"category": "Rent,Groceries,Transport,Dining,Subscriptions,Health,Leisure", "account": "Checking,Savings,Credit card,Brokerage"},
       ["Recent transactions|Date=date;Merchant=pick:Mercado Verde,Metro pass,Spotify,Pharmacy Lux,Café Beira,Uber,Amazon;Amount=money:3,180;Category=pick:Groceries,Transport,Leisure,Health,Dining",
        "Upcoming bills|Bill=pick:Rent,Electricity,Internet,Phone,Insurance,Gym;Due=date;Amount=money:20,1400;Autopay=pick:Yes,No"],
       "Account|Type=pick:Checking,Savings,Credit card;Balance=money:200,18000;Currency=pick:EUR,USD,GBP;Opened=date;Status=pick:Active,Frozen,Review",
       "Link the salary account|Categorise last month|Set the savings goal|Review subscriptions|Schedule the transfer"),
    _d("health", "outpatient clinic",
       ["You are the front-desk assistant for Riverside Family Clinic. You never give medical diagnoses.", "You are Care, a scheduling assistant for a dental and physio clinic."],
       "Appointments today:count:18:92:0:up|No-show rate:pct:2:14:1:down|Average wait:min:4:38:0:down|Patient satisfaction:score:3.6:4.9:1:up|Open slots this week:count:3:40:0:down",
       {"service": "Check-up,Physio,Vaccination,Lab work,Dental,Dermatology", "clinic": "Riverside,Harbour,Old Town"},
       ["Today's schedule|Time=pick:08:30,09:15,10:00,11:30,13:45,15:00,16:20;Patient=person;Service=pick:Check-up,Physio,Vaccination,Lab work,Dental;Room=num:1,9,0",
        "Lab orders|Order=id:LAB;Test=pick:CBC,Lipid panel,HbA1c,Vitamin D,TSH;Status=pick:Collected,In lab,Ready,Pending"],
       "Appointment|Patient=person;Service=pick:Check-up,Physio,Vaccination,Lab work,Dental;Date=date;Room=num:1,9,0;Clinician=person",
       "Collect the insurance card|Take vitals|See the clinician|Book the follow-up|Send the visit summary"),
    _d("travel", "travel planning",
       ["You are Atlas, a trip-planning assistant for a boutique travel agency.", "You are the concierge bot of Wanderline. Friendly but concise."],
       "Trip budget:usd:900:6400:0:down|Flight cost:usd:120:980:0:down|Hotel per night:usd:60:340:0:down|Days booked:count:3:21:0:up|Walking per day:km:4:19:1:up",
       {"city": "Lisbon,Porto,Seville,Valencia,Marseille,Naples", "mode": "Flights,Hotels,Trains,Activities,Food", "season": "Spring,Summer,Autumn,Winter"},
       ["Flight options|Airline=pick:TAP,Iberia,Air France,Ryanair,Vueling,easyJet;Departs=pick:06:40,09:15,12:30,15:05,18:05,21:10;Duration=pick:1h 35m,2h 10m,2h 45m,3h 05m;Price=money:79,420",
        "Hotels|Hotel=pick:Casa Alfama,Hotel Avenida,Porto Riverside,Mar & Sol,Praça Suites,Quinta Verde;Stars=num:3,5,0;Per night=money:60,310;Rating=num:7,9.8,1"],
       "Trip|Destination=city;Dates=pick:Mar 3-7,Apr 14-19,Jun 2-9,Sep 20-24;Travellers=num:1,6,0;Budget=money:600,6000;Status=pick:Planning,Booked,Awaiting payment",
       "Pick the dates|Book the flights|Reserve the hotel|Plan the day trips|Share the itinerary"),
    _d("hr", "recruiting and people ops",
       ["You are the recruiting copilot for a 300-person company.", "You are Talia, an HR assistant. Neutral tone, no legal advice."],
       "Open roles:count:3:48:0:down|Time to hire:days:18:70:0:down|Offer acceptance:pct:55:96:0:up|Applicants this week:count:40:900:0:up|Headcount:count:60:900:0:up|Attrition:pct:3:21:1:down",
       {"stage": "Applied,Screen,Interview,Offer,Hired", "department": "Engineering,Sales,Design,Support,Finance,Operations"},
       ["Candidates|Candidate=person;Role=pick:Backend engineer,Product designer,Account executive,Data analyst,Support lead;Stage=pick:Screen,Interview,Offer,Applied;Score=num:2,5,1",
        "Interviews this week|Day=pick:Mon,Tue,Wed,Thu,Fri;Candidate=person;Panel=pick:Tech,Culture,Hiring manager,Case study;Time=pick:10:00,11:30,14:00,16:15"],
       "Candidate|Role=pick:Backend engineer,Product designer,Account executive,Data analyst;Stage=pick:Screen,Interview,Offer;Source=pick:Referral,LinkedIn,Careers page,Agency;Recruiter=person;Start date=date",
       "Draft the job post|Source candidates|Run the screens|Schedule panel interviews|Send the offer"),
    _d("edu", "online learning platform",
       ["You are the study assistant for Meridian Academy.", "You are Prof, a tutoring assistant for secondary-school maths and science."],
       "Course completion:pct:22:91:0:up|Average quiz score:pct:48:94:0:up|Active learners:count:120:9800:0:up|Assignments due:count:0:12:0:down|Study streak:days:1:60:0:up|Forum questions:count:5:140:0:down",
       {"subject": "Algebra,Biology,Chemistry,History,Physics,Statistics", "level": "Beginner,Intermediate,Advanced"},
       ["Assignments|Assignment=pick:Linear equations set,Cell biology lab,Essay on the Treaty of Utrecht,Newton's laws quiz,Stats project;Due=date;Weight=num:5,40,0;Status=pick:Submitted,Late,Open,Graded",
        "Leaderboard|Student=person;Points=num:120,980,0;Badges=num:0,14,0;Streak=num:1,60,0"],
       "Course|Subject=pick:Algebra,Biology,Chemistry,History,Physics,Statistics;Level=pick:Beginner,Intermediate,Advanced;Lessons=num:8,64,0;Instructor=person;Starts=date",
       "Watch lesson 1|Do the practice set|Take the quiz|Review mistakes|Book office hours"),
    _d("logistics", "freight and last-mile logistics",
       ["You are the dispatch assistant for Orbit Freight.", "You are Route, a logistics assistant for warehouse and delivery teams."],
       "On-time delivery:pct:82:99:1:up|Parcels today:count:300:9800:0:up|Average transit:days:1.2:6.5:1:down|Damage rate:pct:0.1:2.4:1:down|Fleet utilisation:pct:55:94:0:up|Fuel cost:usd_k:3:48:1:down",
       {"carrier": "DHL,UPS,FedEx,Correos,CTT,GLS", "hub": "Porto,Madrid,Lyon,Milan,Rotterdam", "lane": "Iberia,France,Benelux,DACH"},
       ["Shipments|Tracking=id:TRK;Origin=city;Destination=city;Status=pick:In transit,Delivered,Delayed,At customs;ETA=date",
        "Carrier scorecard|Carrier=pick:DHL,UPS,FedEx,Correos,CTT,GLS;On-time=num:78,99,1;Claims=num:0,40,0;Cost per parcel=money:3,19"],
       "Shipment|Tracking=id:TRK;Origin=city;Destination=city;Carrier=pick:DHL,UPS,FedEx,Correos,CTT;Weight kg=num:1,900,0;ETA=date",
       "Pick up at the dock|Scan at the hub|Clear customs|Out for delivery|Collect proof of delivery"),
    _d("realestate", "residential real estate",
       ["You are the listings assistant for Harbour & Co. Realty.", "You are Keystone, an assistant for agents showing homes. Be concise."],
       "Median price:usd_k:180:920:0:up|Days on market:days:9:95:0:down|Active listings:count:30:620:0:up|Showings this week:count:4:90:0:up|Offers received:count:0:14:0:up|Mortgage rate:pct:3.4:7.2:2:down",
       {"neighbourhood": "Old Town,Riverside,Hillcrest,Harbour,Greenfield,Northgate", "type": "Apartment,Townhouse,Detached,Studio,Loft"},
       ["Listings|Address=pick:12 Mill Lane,48 Rua Verde,7 Harbour Row,301 Elm Court,19 Quay Street,5 Orchard Way;Beds=num:1,5,0;Price=money:140,980;Status=pick:Active,Under offer,New,Reduced",
        "Showings|Time=pick:09:30,11:00,13:30,15:00,17:15;Property=pick:12 Mill Lane,48 Rua Verde,7 Harbour Row,19 Quay Street;Buyer=person;Agent=person"],
       "Listing|Address=pick:12 Mill Lane,48 Rua Verde,7 Harbour Row,301 Elm Court;Type=pick:Apartment,Townhouse,Detached,Loft;Beds=num:1,5,0;Area m2=num:38,260,0;Price=money:140,980;Status=pick:Active,Under offer,New",
       "Book the photographer|Publish the listing|Hold the open house|Collect offers|Move to contract"),
    _d("food", "restaurant and delivery",
       ["You are the shift assistant for Brasa, a 60-seat restaurant with delivery.", "You are Chef-bot, a kitchen and floor assistant."],
       "Covers tonight:count:30:260:0:up|Food cost:pct:24:41:1:down|Average ticket:usd:14:62:0:up|Delivery time:min:18:58:0:down|Table turn:min:45:110:0:down|Waste:kg:2:30:1:down",
       {"dish": "Grilled sea bass,Mushroom risotto,Lamb shoulder,Burrata salad,Tonkotsu ramen,Flan", "channel": "Dine-in,Takeaway,Delivery app,Catering"},
       ["Top dishes|Dish=pick:Grilled sea bass,Mushroom risotto,Lamb shoulder,Burrata salad,Tonkotsu ramen,Flan,Charred octopus;Sold=num:12,160,0;Margin=num:38,78,0;Station=pick:Grill,Pasta,Cold,Pastry",
        "Reservations|Time=pick:18:00,18:30,19:15,20:00,20:45,21:30;Name=person;Party=num:2,12,0;Notes=pick:Birthday,Allergy: nuts,Window table,None"],
       "Dish|Station=pick:Grill,Pasta,Cold,Pastry;Price=money:7,38;Allergens=pick:None,Gluten,Dairy,Nuts,Shellfish;Prep time=num:5,40,0;Status=pick:On menu,86'd,Special",
       "Prep the mise en place|Fire the starters|Plate the mains|Send desserts|Close the kitchen"),
    _d("fitness", "fitness coaching app",
       ["You are the coaching assistant in the Stride fitness app.", "You are Coach, a friendly training assistant. Not a doctor."],
       "Weekly distance:km:6:80:1:up|Resting heart rate:bpm:48:78:0:down|Workouts this month:count:3:26:0:up|Sleep:hrs:5.2:8.8:1:up|Calories burned:count:1200:4800:0:up|Body fat:pct:9:32:1:down",
       {"activity": "Running,Cycling,Swimming,Strength,Yoga,Hiking", "day": "Mon,Tue,Wed,Thu,Fri,Sat,Sun"},
       ["Workout log|Date=date;Activity=pick:Running,Cycling,Swimming,Strength,Yoga;Duration=num:20,120,0;Calories=num:150,980,0",
        "Plan this week|Day=pick:Mon,Tue,Wed,Thu,Fri,Sat,Sun;Session=pick:Intervals,Long run,Upper body,Mobility,Rest,Tempo;Minutes=num:0,90,0"],
       "Athlete|Goal=pick:10K in under 50 min,Half marathon,Build muscle,Lose 5 kg;Weekly sessions=num:2,6,0;Coach=person;Plan=pick:Base,Build,Peak,Taper;Next test=date",
       "Warm up|Main set|Cool down|Log the session|Plan tomorrow"),
    _d("energy", "utilities and energy",
       ["You are the energy-usage assistant for Voltaic, a household utilities app.", "You are Watt, an assistant for building managers."],
       "Consumption:kwh:180:1200:0:down|Solar generation:kwh:20:520:0:up|Peak demand:kw:2.1:11.5:1:down|Bill estimate:usd:48:310:0:down|Grid carbon:pct:12:68:0:down|Battery level:pct:8:100:0:up",
       {"appliance": "Heating,Water heater,Fridge,Laundry,Lighting,EV charger", "source": "Solar,Grid,Battery,Wind"},
       ["Daily usage|Day=pick:Mon,Tue,Wed,Thu,Fri,Sat,Sun;Usage kWh=num:6,48,0;Peak hour=pick:07:00,08:00,18:00,19:00,20:00;Cost=money:1,15",
        "Devices|Device=pick:Heat pump,Dishwasher,EV charger,Dryer,Pool pump,Oven;Power kW=num:0.1,7.4,1;Status=pick:On,Off,Scheduled,Fault"],
       "Meter|Meter id=id:MTR;Tariff=pick:Flat,Time-of-use,Green;Last reading=num:1000,98000,0;Read on=date;Status=pick:OK,Check,Offline",
       "Read the meter|Compare tariffs|Shift the heavy loads|Install the smart plug|Review next bill"),
    _d("marketing", "performance marketing",
       ["You are the campaign assistant for a growth-marketing agency.", "You are Spark, a reporting assistant for paid media managers."],
       "Ad spend:usd_k:2:60:1:down|ROAS:ratio:1.1:6.5:1:up|Click-through rate:pct:0.6:4.8:1:up|Cost per lead:usd:6:90:0:down|Leads:count:60:2200:0:up|Email open rate:pct:14:46:1:up",
       {"channel": "Search,Social,Display,Email,Influencer,Affiliate", "campaign": "Spring launch,Brand refresh,Winter sale,Webinar series,App install"},
       ["Campaigns|Campaign=pick:Spring launch,Brand refresh,Winter sale,Webinar series,App install;Spend=money:400,38000;Leads=num:30,1400,0;CPL=money:6,80",
        "Creative tests|Variant=pick:A,B,C,D;Headline=pick:Save 20% today,Built for busy teams,See it in action,Free for 14 days;CTR=num:0.4,5,1;Winner=pick:Yes,No,Running"],
       "Campaign|Channel=pick:Search,Social,Display,Email;Budget=money:1000,60000;Start=date;Owner=person;Status=pick:Draft,Live,Paused,Ended",
       "Write the brief|Build the audiences|Launch the creatives|Monitor the first 48 hours|Report the results"),
    _d("support", "customer support desk",
       ["You are the support-desk assistant for Helpwave.", "You are Sage, a helper for tier-1 support agents."],
       "First response time:min:3:95:0:down|CSAT:pct:70:98:0:up|Open tickets:count:20:700:0:down|Backlog age:days:0.5:9:1:down|Resolved today:count:15:340:0:up|Escalations:count:0:30:0:down",
       {"queue": "Billing,Technical,Account,Shipping,Feedback", "priority": "Low,Normal,High,Urgent"},
       ["Open tickets|ID=id:TCK;Subject=pick:Refund not received,Cannot reset password,Invoice shows wrong VAT,App crashes on launch,Where is my parcel,Change billing email;Priority=pick:Low,Normal,High,Urgent;Agent=person",
        "Agent performance|Agent=person;Resolved=num:12,90,0;CSAT=num:78,99,0;Avg handle=num:4,22,0"],
       "Ticket|ID=id:TCK;Customer=person;Queue=pick:Billing,Technical,Account,Shipping;Priority=pick:Low,Normal,High,Urgent;Opened=date;Status=pick:Open,Pending,Solved",
       "Acknowledge the customer|Reproduce the issue|Escalate to tier 2|Confirm the fix|Close the ticket"),
    _d("legal", "contract management",
       ["You are the contracts assistant for the in-house legal team. You give no legal advice.", "You are Clause, a contract-tracking assistant."],
       "Contracts expiring in 90 days:count:2:60:0:down|Average review time:days:1:14:1:down|Open redlines:count:0:40:0:down|Signed this month:count:3:70:0:up|NDAs pending:count:0:25:0:down",
       {"type": "NDA,MSA,SOW,DPA,Lease,Employment", "status": "Draft,In review,Out for signature,Signed,Expired"},
       ["Contracts|Counterparty=pick:Acme,Northwind,Globex,Initech,Hooli,Soylent;Type=pick:NDA,MSA,SOW,DPA;Value=money:5000,480000;Expires=date",
        "Redlines|Clause=pick:Limitation of liability,Termination,Data processing,Payment terms,Governing law;Owner=person;Status=pick:Open,Accepted,Countered"],
       "Contract|Counterparty=pick:Acme,Northwind,Globex,Initech;Type=pick:NDA,MSA,SOW,DPA;Signed=date;Expires=date;Owner=person;Status=pick:Draft,In review,Signed",
       "Draft from the template|Legal review|Counterparty redlines|Final approval|Signature"),
    _d("manufacturing", "plant operations",
       ["You are the shop-floor assistant for Kiln & Co. Works.", "You are Gauge, a line-supervisor assistant. Short, factual."],
       "OEE:pct:48:92:0:up|Scrap rate:pct:0.4:7:1:down|Units produced:count:800:24000:0:up|Downtime:min:5:240:0:down|Cycle time:sec:12:95:0:down|Energy per unit:kwh:0.8:6.4:1:down",
       {"line": "Line A,Line B,Line C,Packaging,Paint shop", "shift": "Morning,Afternoon,Night"},
       ["Machines|Machine=id:M;Line=pick:Line A,Line B,Line C,Packaging;Status=pick:Running,Idle,Down,Maintenance;Last service=date",
        "Quality checks|Batch=id:B;Defects=num:0,28,0;Inspector=person;Result=pick:Pass,Rework,Reject"],
       "Machine|Machine=id:M;Line=pick:Line A,Line B,Line C;Status=pick:Running,Idle,Down;Last service=date;Operator=person;Output per hour=num:40,900,0",
       "Set up the line|Run the first article|Full production|Quality sampling|Changeover"),
    _d("agri", "farm management",
       ["You are the field assistant for Greenacre Farm Co-op.", "You are Sprout, an agronomy helper. You do not give pesticide dosages."],
       "Yield:t:2.1:11:1:up|Soil moisture:pct:14:48:0:up|Rainfall:mm:0:140:0:up|Irrigation:kl:4:90:0:down|Fuel use:l:30:900:0:down|Harvest progress:pct:0:100:0:up",
       {"crop": "Wheat,Barley,Maize,Sunflower,Olives,Tomatoes", "field": "North 40,River plot,Hill field,Orchard,Greenhouse"},
       ["Fields|Field=pick:North 40,River plot,Hill field,Orchard,Greenhouse;Crop=pick:Wheat,Barley,Maize,Sunflower,Olives;Hectares=num:2,60,0;Stage=pick:Sowing,Growing,Flowering,Harvest",
        "Equipment|Machine=pick:John Deere 6130,Claas Lexion,Kubota M7,Sprayer S2,Baler B1;Hours=num:120,5400,0;Status=pick:Ready,In field,Service due"],
       "Field|Crop=pick:Wheat,Barley,Maize,Sunflower;Hectares=num:2,60,0;Sown=date;Soil=pick:Clay,Loam,Sandy,Silt;Irrigation=pick:Drip,Pivot,Rain-fed",
       "Prepare the soil|Sow the seed|Irrigate and monitor|Harvest|Store and sell", True),
    _d("gaming", "live-ops for a mobile game",
       ["You are the live-ops analyst for Pixelforge Studios.", "You are Pip, a game-economy assistant for designers."],
       "Daily active users:count:8000:420000:0:up|Day-7 retention:pct:6:28:1:up|ARPDAU:usd:0.05:0.9:2:up|Session length:min:4:26:0:up|Crash rate:pct:0.05:2.2:2:down|Pre-orders:count:300:48000:0:up",
       {"mode": "Solo,Co-op,Ranked,Events,Practice", "platform": "iOS,Android,PC,Console"},
       ["Events|Event=pick:Spring Festival,Boss Rush,Double XP Weekend,Lunar Hunt,Speedrun Cup;Players=num:2000,160000,0;Revenue=money:1000,90000;Status=pick:Live,Scheduled,Ended",
        "Bugs|ID=id:BUG;Title=pick:Inventory duplicates,Lag on arena map,Daily reward not granted,Audio cuts out,Matchmaking stuck;Severity=pick:Minor,Major,Critical;Owner=person"],
       "Event|Mode=pick:Solo,Co-op,Ranked,Events;Starts=date;Duration days=num:2,21,0;Reward=pick:Skin,Gems,Loot box,Title;Status=pick:Scheduled,Live,Ended",
       "Design the event|Balance the rewards|Playtest|Ship the build|Monitor the economy"),
    _d("media", "music streaming",
       ["You are the editorial assistant for Tidal Waves, a streaming service.", "You are Mix, a playlist assistant."],
       "Monthly listeners:count:12000:4800000:0:up|Streams:count:90000:36000000:0:up|Skip rate:pct:12:46:0:down|Playlist adds:count:300:90000:0:up|Royalties:usd_k:1:160:1:up|Podcast downloads:count:800:210000:0:up",
       {"genre": "Indie,Electronic,Jazz,Hip hop,Classical,Latin", "format": "Singles,Albums,Playlists,Podcasts"},
       ["Top tracks|Track=pick:Neon Harbour,Slow Weather,Paper Lanterns,Static Bloom,Midnight Tram,Salt & Honey;Artist=person;Streams=num:20,900,0;Skips=num:5,50,0",
        "Release calendar|Date=date;Release=pick:Neon Harbour EP,Slow Weather,Paper Lanterns LP,Static Bloom;Artist=person;Format=pick:Single,EP,Album"],
       "Track|Artist=person;Genre=pick:Indie,Electronic,Jazz,Hip hop,Classical;Length=pick:2:48,3:21,3:55,4:30,5:12;Released=date;Streams=num:20,900,0",
       "Pitch to editors|Master the track|Upload the artwork|Schedule the release|Promote on socials"),
    _d("insurance", "insurance claims",
       ["You are the claims assistant for Shieldwell Insurance. You do not decide coverage.", "You are Claimy, a helper for claims adjusters."],
       "Open claims:count:40:1400:0:down|Average settlement:usd:480:12000:0:down|Days to settle:days:3:40:0:down|Fraud flags:count:0:60:0:down|Approval rate:pct:60:96:0:up|Claims this week:count:12:260:0:up",
       {"type": "Auto,Home,Travel,Health,Pet", "status": "Filed,Assessing,Approved,Paid,Denied"},
       ["Claims|Claim=id:CLM;Type=pick:Auto,Home,Travel,Health,Pet;Amount=money:150,18000;Status=pick:Filed,Assessing,Approved,Paid;Adjuster=person",
        "Policies expiring|Policy=id:POL;Holder=person;Type=pick:Auto,Home,Travel,Pet;Expires=date;Premium=money:80,2400"],
       "Claim|Claim=id:CLM;Type=pick:Auto,Home,Travel,Health,Pet;Filed=date;Amount=money:150,18000;Adjuster=person;Status=pick:Filed,Assessing,Approved,Paid",
       "File the claim|Collect the documents|Assess the damage|Approve the amount|Issue the payment"),
    _d("telecom", "mobile and broadband provider",
       ["You are the account assistant for Nimbus Mobile.", "You are Signal, a network-operations helper."],
       "Data used:gb:1:120:1:down|Download speed:mbps:20:900:0:up|Latency:ms:8:90:0:down|Dropped calls:pct:0.1:3.5:1:down|Subscribers:count:2000:880000:0:up|Churn:pct:0.8:3.4:1:down",
       {"plan": "Basic,Plus,Max,Family,Business", "tower": "North,South,Harbour,Airport,Campus"},
       ["Plans|Plan=pick:Basic,Plus,Max,Family,Business;Data GB=num:5,200,0;Speed Mbps=num:50,1000,0;Price=money:9,69",
        "Outages|ID=id:OUT;Area=city;Cause=pick:Fibre cut,Power failure,Software update,Congestion;Status=pick:Investigating,Fixed,Monitoring;Customers=num:40,12000,0"],
       "Subscription|Plan=pick:Basic,Plus,Max,Family,Business;Data GB=num:5,200,0;Price=money:9,69;Renews=date;Lines=num:1,5,0;Status=pick:Active,Suspended,Pending port-in",
       "Verify the account|Run the line test|Reset the router|Escalate to field tech|Confirm the fix"),
    _d("nonprofit", "nonprofit fundraising",
       ["You are the donor-relations assistant for Open Hands Foundation.", "You are Hope, a fundraising-reporting assistant."],
       "Donations this month:usd_k:2:180:1:up|Active donors:count:300:19000:0:up|Retention:pct:28:72:0:up|Volunteer hours:hrs:60:2400:0:up|Grant applications:count:1:22:0:up|Campaign goal reached:pct:10:130:0:up",
       {"program": "Clean water,School meals,Reforestation,Legal aid,Emergency relief", "source": "Individuals,Corporate,Grants,Events"},
       ["Donors|Donor=person;Last gift=money:10,5000;Gifts=num:1,40,0;Segment=pick:Major,Mid-level,Monthly,Lapsed",
        "Grants|Funder=pick:Lakeshore Trust,Meridian Fund,Sunrise Foundation,City Arts Board;Amount=money:5000,200000;Deadline=date;Status=pick:Drafting,Submitted,Awarded,Declined"],
       "Campaign|Program=pick:Clean water,School meals,Reforestation,Legal aid;Goal=money:5000,250000;Raised=money:1000,200000;Ends=date;Lead=person",
       "Set the goal|Write the appeal|Send to the list|Thank the donors|Report the impact", True),
    _d("events", "event ticketing",
       ["You are the box-office assistant for Encore Tickets.", "You are Stage, an event-ops assistant."],
       "Tickets sold:count:120:18000:0:up|Revenue:usd_k:3:260:1:up|Capacity filled:pct:30:100:0:up|Refund requests:count:0:90:0:down|Check-in wait:min:1:25:0:down|Waitlist:count:0:1800:0:up",
       {"tier": "General,VIP,Early bird,Student,Group", "venue": "Main Hall,Arena,Rooftop,Studio"},
       ["Events|Event=pick:Jazz on the Quay,Tech Summit,Food Fest,Indie Film Night,Marathon Expo;Date=date;Sold=num:80,9000,0;Venue=pick:Main Hall,Arena,Rooftop,Studio",
        "Orders|Order=id:EVT;Buyer=person;Tickets=num:1,8,0;Tier=pick:General,VIP,Early bird,Student;Total=money:20,900"],
       "Event|Venue=pick:Main Hall,Arena,Rooftop,Studio;Date=date;Doors=pick:17:30,18:00,19:00,20:00;Capacity=num:120,12000,0;Sold=num:50,11000,0;Status=pick:On sale,Sold out,Postponed",
       "Confirm the venue|Open ticket sales|Announce the line-up|Run check-in|Send the thank-you"),
    _d("auto", "fleet management",
       ["You are the fleet assistant for CityMove, a vehicle-rental company.", "You are Odo, a maintenance-planning helper."],
       "Fleet availability:pct:60:98:0:up|Miles driven:count:4000:260000:0:up|Fuel economy:mpg:24:58:0:up|Maintenance backlog:count:0:34:0:down|Idle time:pct:5:35:0:down|Accidents:count:0:9:0:down",
       {"vehicle": "Compact,SUV,Van,Pickup,EV", "depot": "Central,Airport,Harbour,Campus"},
       ["Vehicles|Plate=id:CM-;Model=pick:Corolla,Transit,Model 3,Ranger,Kona,Golf;Mileage=num:2000,160000,0;Status=pick:Available,Rented,In service,Out of order",
        "Service due|Plate=id:CM-;Service=pick:Oil change,Brake pads,Tyres,Battery check,Annual inspection;Due=date;Depot=pick:Central,Airport,Harbour,Campus"],
       "Vehicle|Plate=id:CM-;Model=pick:Corolla,Transit,Model 3,Ranger,Kona,Golf;Mileage=num:2000,160000,0;Depot=pick:Central,Airport,Harbour,Campus;Next service=date;Status=pick:Available,Rented,In service",
       "Inspect the vehicle|Book the service slot|Swap the tyres|Road test|Return to the pool", True),
]

DOMAIN_BY_KEY = {d.key: d for d in DOMAINS}
PERSONA_SUFFIX = ["", "", "", " Keep answers short.", " Answer in the user's language.", " Be warm but efficient.",
                  " Never speculate beyond the data you are given."]
