import { Translator } from "@/components/translator";

export default function Home() {
  return (
    <>
      <header className="masthead">
        <p className="wordmark">v2c translator</p>
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
      </main>
      <footer className="page-footer">
        <p>
          This tool is not affiliated with or endorsed by the Department of Defense, any branch of the Armed Forces, or
          the Department of Labor.
        </p>
      </footer>
    </>
  );
}
