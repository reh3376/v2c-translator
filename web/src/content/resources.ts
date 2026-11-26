/**
 * The "Resources for veterans" links.
 *
 * Every link is a plain address with no query string and no tracking parameter, and opens in a new
 * tab. Nothing here is loaded by the page, so the self-only Content-Security-Policy is untouched:
 * following a link is navigation, not a subresource fetch.
 *
 * `scripts/check-links.mjs` reads this file and reports dead links. It runs on a schedule and on
 * demand, never in pull-request CI, because these sites are outside this repository's control.
 *
 * Each address was checked on 2026-11-26. Two of them replace the ones first proposed:
 * skillbridge.osd.mil now redirects to www.skillbridge.mil, and the VA's
 * /careers-employment/vocational-rehabilitation/ redirects to /careers-employment/vre/.
 */

export interface Resource {
  readonly title: string;
  readonly href: string;
  /** One line on what the reader gets there. */
  readonly blurb: string;
}

export interface ResourceGroup {
  readonly heading: string;
  readonly links: readonly Resource[];
}

export const RESOURCE_GROUPS: readonly ResourceGroup[] = [
  {
    heading: "Your records",
    links: [
      {
        title: "Request military service records",
        href: "https://www.archives.gov/veterans/military-service-records",
        blurb: "The National Archives holds separation records. Veterans and next of kin order copies free.",
      },
      {
        title: "milConnect",
        href: "https://milconnect.dmdc.osd.mil/milconnect/",
        blurb: "Sign in to download your VMET and, for recent separations, your DD-214.",
      },
    ],
  },
  {
    heading: "Work and transition",
    links: [
      {
        title: "DoD SkillBridge",
        href: "https://www.skillbridge.mil/",
        blurb: "Civilian training and internships during your last months of service.",
      },
      {
        title: "Veterans' Employment and Training Service",
        href: "https://www.dol.gov/agencies/vets",
        blurb: "The Department of Labor agency for veteran employment, including USERRA job rights.",
      },
      {
        title: "CareerOneStop Veteran and Military Transition Center",
        href: "https://www.careeronestop.org/Veterans/default.aspx",
        blurb: "Job search, training and benefits in one place, funded by the Department of Labor.",
      },
      {
        title: "My Next Move for Veterans",
        href: "https://www.mynextmove.org/vets/",
        blurb: "Enter a military job title and read the civilian careers O*NET matches to it.",
      },
      {
        title: "DoD COOL",
        href: "https://www.cool.osd.mil/",
        blurb: "Credentials and licences your occupation counts toward. Each service's COOL site links from here.",
      },
      {
        title: "Hire Heroes USA",
        href: "https://www.hireheroesusa.org/",
        blurb: "Free one-to-one career coaching and resume help for veterans and military spouses.",
      },
    ],
  },
  {
    heading: "Benefits",
    links: [
      {
        title: "VA benefits and health care",
        href: "https://www.va.gov/",
        blurb: "Apply for and manage disability, health care, housing and education benefits.",
      },
      {
        title: "Veteran Readiness and Employment",
        href: "https://www.va.gov/careers-employment/vre/",
        blurb: "Chapter 31. Training, education and job help for veterans with a service-connected disability.",
      },
      {
        title: "GI Bill",
        href: "https://www.va.gov/education/about-gi-bill-benefits/",
        blurb: "What the GI Bill pays for, who qualifies, and how to transfer it to a family member.",
      },
    ],
  },
];

/**
 * The Veterans Crisis Line, as it is worded on veteranscrisisline.net. Shown plainly, not as a
 * styled call to action, and never behind a disclosure.
 */
export const CRISIS_LINE = {
  dial: "988",
  press: "1",
  text: "838255",
  href: "https://www.veteranscrisisline.net/",
  site: "VeteransCrisisLine.net",
} as const;

/** Every address the link checker visits. */
export const ALL_LINKS: readonly string[] = [
  ...RESOURCE_GROUPS.flatMap((group) => group.links.map((link) => link.href)),
  CRISIS_LINE.href,
];
