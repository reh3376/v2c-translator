import { CalmMotion } from "@/components/calm-motion";
import { Resources } from "@/components/resources";
import { ThemeControl } from "@/components/theme-control";
import { Translator } from "@/components/translator";

export default function Home() {
  return (
    <CalmMotion>
      <header className="masthead">
        <p className="wordmark">v2c translator</p>
        <ThemeControl />
      </header>
      <main>
        <div className="intro">
          <h1>Translate your service record into civilian keywords</h1>
          <p className="lede">
            Add your DD-214s, any DD-215 corrections and your VMET. You get civilian job titles, skills, technologies
            and a keyword string ready for job applications.
          </p>
        </div>
        <Translator />
        <Resources />
      </main>
      <footer className="page-footer">
        <p>
          This tool is not affiliated with or endorsed by the Department of Defense, any branch of the Armed Forces, or
          the Department of Labor. The pictures are original illustrations and use no service seal, emblem, logo or
          insignia.
        </p>
      </footer>
    </CalmMotion>
  );
}
