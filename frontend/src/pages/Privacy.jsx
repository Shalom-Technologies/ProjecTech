import { Link } from "react-router-dom";
import LegalPage from "../components/LegalPage";
import { openCookieSettings } from "../consent";

export default function Privacy() {
  return (
    <LegalPage title="Privacy Policy" updated="22 October 2026">
      <p>
        This policy explains what personal data ProjecTech collects, why, who sees it, and what
        you can do about it. Shalom Technologies Limited, a company in Nairobi, Kenya, runs
        ProjecTech and decides how your data is used. Under the Kenya Data Protection Act, 2019,
        that makes us the data controller. Questions and requests go to privacy@projectech.dev.
        Our <Link to="/terms">Terms of Service</Link> explain the rest of the agreement.
      </p>

      <h2>What we collect</h2>
      <h3>When you create and use an account</h3>
      <ul>
        <li>
          Your name, email address and password. We store only a scrambled (hashed) form of the
          password, so we cannot read it.
        </li>
        <li>
          Your role, your skills if you are a developer, or your company name if you are a
          salesperson.
        </li>
        <li>Optional profile details: phone number, bio and location.</li>
        <li>The M-Pesa number and name you add to receive payouts.</li>
        <li>
          Projects you post, applications and cover letters you send, messages you exchange,
          reviews you write and problem reports you file.
        </li>
        <li>Your wallet balance, your earnings, and a history of your payments and withdrawals.</li>
        <li>The date you agreed to our terms.</li>
      </ul>

      <h3>About clients</h3>
      <p>
        When a salesperson posts a project, they give us the client's name and email address. We
        use them to send the payment link and the review email, and to show the client's name on
        the invoice. A client may never have used ProjecTech. Clients pay on Paystack's page. We
        receive the payment's status, reference and amount, and we never see card numbers or
        M-Pesa PINs. If you are a client and want to know what we hold about you, or want it
        removed, email us.
      </p>

      <h3>Collected automatically</h3>
      <ul>
        <li>
          Your IP address and request details, which our servers see whenever you use the site.
          We use them to keep the site running, to block abuse and to limit repeated login
          attempts.
        </li>
        <li>A login token stored in your browser so you stay signed in.</li>
        <li>
          Usage statistics from Google Analytics, only if you accept analytics in the cookie
          banner: pages viewed, device and browser type, approximate location worked out from
          your IP address, and the cookies Google Analytics sets.
        </li>
        <li>
          A record of any email we could not send: the address, the kind of email and the error.
          We keep it so we can fix delivery problems.
        </li>
      </ul>

      <h2>Why we use it</h2>
      <p>The Data Protection Act requires a lawful reason for each use. Ours are these.</p>
      <ul>
        <li>
          To run your account, match projects, take payments and pay you. This is needed to give
          you the service you signed up for.
        </li>
        <li>
          To email you about your account, payments, reviews and security. This is part of the
          service, and we have a legitimate interest in keeping you informed.
        </li>
        <li>
          To look into problem reports and refunds. This is part of the service, and we have a
          legitimate interest in settling disputes fairly.
        </li>
        <li>
          To prevent fraud and abuse and to keep the site secure. This is our legitimate interest,
          and sometimes a legal duty.
        </li>
        <li>
          To keep financial records and answer tax and legal requests. This is a legal duty.
        </li>
        <li>
          To see how the site is used and improve it with Google Analytics. We do this only if you
          accept analytics in the cookie banner, so your consent is the ground. You can withdraw
          it at any time.
        </li>
      </ul>
      <p>We do not sell your personal data.</p>

      <h2>Who sees your data</h2>
      <h3>Other users</h3>
      <p>
        A salesperson sees the name, email address, cover letter and price of every developer who
        applies to their project. A developer sees a project's description and the name of the
        salesperson who posted it. The client's email address is shown only to the salesperson who
        posted the project, and the client's name only to that salesperson and the developer
        assigned to the project. People you message see your name and what you write. Reviews are
        shown with the reviewer's name.
      </p>
      <h3>Companies that help us run ProjecTech</h3>
      <ul>
        <li>
          Paystack takes payments and sends payouts. It receives the payer's email address, the
          amount, and the M-Pesa number and name of the person being paid. It handles that data
          under its own privacy policy.
        </li>
        <li>
          Resend sends our emails. It receives the recipient's email address and the content of
          the message.
        </li>
        <li>MongoDB Atlas stores our database, on Amazon Web Services in Cape Town.</li>
        <li>Fly.io runs our server in Johannesburg.</li>
        <li>Render hosts the website's files and sees the IP address of each visitor.</li>
        <li>Google provides Google Analytics and the Google Fonts typeface.</li>
      </ul>
      <p>
        Except for Paystack, which acts for itself when it handles payments, these companies may
        use the data only to provide their service to us.
      </p>
      <h3>Authorities and buyers</h3>
      <p>
        We share data with courts, the police and regulators, including the Office of the Data
        Protection Commissioner and the Kenya Revenue Authority, when the law requires it. If we
        sell or merge the business, your data goes to the new owner, who must keep to this policy.
      </p>

      <h2>Where your data goes</h2>
      <p>
        Our database is in South Africa and our server is in Johannesburg. Some of our providers
        process data in other countries. Resend and Google may do so in the United States.
        Paystack and Render process it where they operate. The Data Protection Act allows
        transfers abroad when the data is properly protected. We choose providers whose contracts
        require them to protect personal data.
      </p>

      <h2 id="cookies">Cookies and local storage</h2>
      <p>
        ProjecTech keeps a login token in your browser's local storage. The site needs it to
        keep you signed in, so you cannot switch it off. It expires after 60 minutes and is
        removed when you log out.
      </p>
      <p>
        Google Analytics sets cookies to count visitors and see which pages are used. It is off
        until you accept it in the cookie banner. Until then the analytics script is not loaded,
        and if you decline it never is. If you accept and later change
        your mind, we stop the measurement and delete the Google Analytics cookies that your
        browser holds for our site. We remember your choice in your browser's local storage.
      </p>
      <p>
        The site also loads its typeface from Google Fonts. That means Google receives your IP
        address when a page loads, whatever you choose in the banner. Google Fonts sets no
        cookies.
      </p>
      <p>
        <button type="button" className="link-button" onClick={openCookieSettings}>
          Change your cookie choice
        </button>
      </p>

      <h2>How long we keep it</h2>
      <ul>
        <li>
          Account details stay while your account is open. After you ask us to close it, we delete
          or anonymise them, except what we list below.
        </li>
        <li>
          Payment, wallet and invoice records, and any problem report attached to a payment, stay
          for 7 years after the transaction, even if the account is closed. We need them for tax
          and accounting.
        </li>
        <li>
          Confirmation and password reset links work once and expire. We store
          only a hashed copy.
        </li>
      </ul>

      <h2>Security</h2>
      <p>
        Passwords, confirmation links and reset links are stored in hashed form. Traffic to the
        site is encrypted, repeated login attempts are limited, and access to the database is
        limited to the people who run ProjecTech. No system is perfectly secure. If a breach is
        likely to harm you, we will tell you and the Data Protection Commissioner within 72 hours
        of learning about it, as the law requires.
      </p>

      <h2>Your rights</h2>
      <p>Under the Data Protection Act you can:</p>
      <ul>
        <li>ask what personal data we hold about you and get a copy</li>
        <li>have wrong data corrected</li>
        <li>ask us to delete your data, except what we must keep by law</li>
        <li>object to or limit how we use your data</li>
        <li>receive your data in a common format to take elsewhere</li>
        <li>withdraw consent where we rely on it</li>
      </ul>
      <p>
        Email privacy@projectech.dev from the address on your account so we can check it is you.
        We answer within the time the Act sets. You can change your name, phone number, bio and
        location yourself in Settings. We cannot delete an account while a payment is held or a
        problem report is open, so we finish those first.
      </p>
      <p>
        If you are not happy with our answer, you can complain to the Office of the Data
        Protection Commissioner of Kenya at odpc.go.ke.
      </p>

      <h2>Children</h2>
      <p>
        ProjecTech is for people aged 18 and over. If we learn that an account belongs to someone
        under 18, we will close it and delete its data.
      </p>

      <h2>Changes to this policy</h2>
      <p>
        We may change this policy. We will post the new version here with a new date. For changes
        that affect how we use your data, we will also email you before they start.
      </p>

      <h2>Contact</h2>
      <p>
        Shalom Technologies Limited, Nairobi, Kenya. Email privacy@projectech.dev.
      </p>
    </LegalPage>
  );
}
