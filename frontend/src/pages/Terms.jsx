import { Link } from "react-router-dom";
import LegalPage from "../components/LegalPage";

export default function Terms() {
  return (
    <LegalPage title="Terms of Service" updated="22 October 2026">
      <p>
        These terms are the agreement between you and Shalom Technologies Limited, a company in
        Nairobi, Kenya ("we", "us"). We run ProjecTech at projectech.dev. You agree to them when
        you create an account, pay an invoice we send you, or use the site. If you do not agree,
        do not use ProjecTech. Our <Link to="/privacy">Privacy Policy</Link> explains how we
        handle personal data and is part of this agreement.
      </p>

      <h2>What ProjecTech is</h2>
      <p>
        ProjecTech connects salespeople who find clients with developers who build software for
        them. A salesperson posts a project for a client and developers apply. The salesperson
        picks one. The client pays ProjecTech, we hold the money while the work is done, and we
        release it when the client accepts the work or the review period ends.
      </p>
      <p>
        A salesperson has an account and posts projects. A developer has an account and builds
        them. A client is the person or business a project is for. A client does not need an
        account and pays through a link we email to them. By paying, the client agrees to these
        terms for that project.
      </p>
      <p>
        Developers and salespeople are independent. They are not our employees, partners or
        agents, and we do not supervise their work. We run the platform and handle the payment.
        We do not promise that a project will find a developer, that a developer will finish it,
        or that the work will be good.
      </p>

      <h2>Your account</h2>
      <ul>
        <li>You must be at least 18 years old.</li>
        <li>You must give true details and keep them up to date.</li>
        <li>You choose one role, developer or salesperson, when you sign up.</li>
        <li>
          You must confirm your email address before you can apply for projects, post projects,
          pay or withdraw money.
        </li>
        <li>
          You are responsible for everything done under your account. Keep your password private
          and tell us at once if someone else gets in.
        </li>
      </ul>

      <h2>How a project works</h2>
      <ol>
        <li>
          The salesperson posts the project with a budget and the client's name and email
          address. The salesperson must have the client's permission to give us that address.
        </li>
        <li>Developers apply with a cover letter and a price.</li>
        <li>
          The salesperson accepts one application. The accepted price becomes the agreed price.
          It is the only amount we invoice.
        </li>
        <li>
          A later price change needs the developer's approval. Until the developer answers, we do
          not invoice the client.
        </li>
        <li>
          We email the client a payment link. The client pays through Paystack in Kenyan
          shillings, by M-Pesa or card.
        </li>
        <li>We hold the money. The developer starts work once the project shows as funded.</li>
        <li>
          The developer marks the project as delivered and we email the client a link to review
          it. The client has 7 days.
        </li>
        <li>
          If the client accepts, or 7 days pass without an objection, we release the payment. If
          the client, the salesperson or the developer reports a problem, we stop the release
          until we have looked into it.
        </li>
      </ol>
      <p>
        We set a smallest and a largest payment for one project. They are currently KES 100 and
        KES 5,000,000. A payment link works for one project at one price. If the price changes,
        the old link stops working, and anything paid through it is refunded.
      </p>
      <p>
        A project with no payment held can be cancelled. After a full refund, the salesperson can
        reopen the project and choose a new developer. The earlier developer is removed from it.
      </p>

      <h2>Money</h2>
      <h3>Fees and the split</h3>
      <p>
        The client pays the agreed price and nothing on top. We divide it: 45% to the developer,
        35% to the salesperson and 20% to ProjecTech. We pay Paystack's charges for taking the
        payment and sending payouts out of our 20%.
      </p>
      <p>
        We can change the split for projects that are not yet funded. We will post the change on
        this page and email you at least 30 days before it starts. It never changes a project
        that is already funded.
      </p>
      <h3>Taxes</h3>
      <p>
        You are responsible for any tax on what you earn. We do not withhold or pay tax for you
        unless the law requires us to.
      </p>
      <h3>Payouts</h3>
      <p>
        Released earnings go to your ProjecTech wallet. They wait there for 7 days before you can
        withdraw them, which protects against card chargebacks. You withdraw to an M-Pesa number
        you add in your wallet. Check it carefully, because we cannot recover money sent to a
        wrong number you gave us. A withdrawal that fails goes back to your wallet.
      </p>
      <p>
        Your wallet is not a bank account. It earns no interest and is not insured. If a payment
        is reversed after we released it, for example by a card chargeback, we may take that
        amount back from your wallet or from your later earnings. We may delay or refuse a payout
        while we look into fraud, a legal request or a breach of these terms. We will tell you
        why unless the law stops us.
      </p>

      <h2>Problems and refunds</h2>
      <p>
        While a payment is held, the client, the salesperson or the developer can report a
        problem from the project page or the client's review link. A report stops the release. We
        read what each side says and may ask for evidence such as messages, files and
        screenshots. Then we decide one of three outcomes:
      </p>
      <ul>
        <li>release the full payment</li>
        <li>refund the client in full</li>
        <li>
          refund part and release the rest, with the developer's and salesperson's shares worked
          out again on the amount that remains
        </li>
      </ul>
      <p>
        Our decision settles how the held money is paid out. It does not take away anyone's right
        to go to court or any right they have under Kenyan law.
      </p>
      <p>
        Refunds go back to the client through Paystack and can take several days to arrive. A
        payment made on a retired link, or after a project was cancelled, is refunded in full.
        Once a payment has been released we cannot refund it. A client who is unhappy after that
        has to settle it with the developer and the salesperson.
      </p>

      <h2>Who owns the work</h2>
      <p>
        The client owns the finished work for a project from the moment its payment is released
        to the developer. Until then the developer owns it and lets the client look at it and
        test it for the review.
      </p>
      <p>
        The developer keeps their own tools, libraries and code that existed before the project.
        If any of that is built into the work, the client gets a permanent right to use it as
        part of the work. Open-source parts stay under their own licences. A developer must
        deliver work they have the right to hand over, and must not copy other people's work or
        break a licence.
      </p>

      <h2>What you post</h2>
      <p>
        You own what you post: project descriptions, applications, profile details, messages and
        reviews. You give us permission to store it, show it and send it as needed to run
        ProjecTech. Post only what you have the right to post. Reviews must be honest and based
        on real work done through ProjecTech. We may remove content that breaks these terms.
      </p>

      <h2>Keeping deals on ProjecTech</h2>
      <p>
        When ProjecTech brings a salesperson, a developer and a client together on a project, the
        payment for that project goes through ProjecTech. So does the payment for any follow-on
        work for the same client that comes from that introduction. You must not agree to move
        payment elsewhere to avoid our 20%. If you do, we may suspend or close your account.
      </p>

      <h2>Rules for using ProjecTech</h2>
      <p>You must not:</p>
      <ul>
        <li>break the law, or use ProjecTech to launder money or move the proceeds of a crime</li>
        <li>post a project for a client who does not exist</li>
        <li>give us a client's email address without that client's permission</li>
        <li>pretend to be someone else, or write fake reviews</li>
        <li>harass, threaten or discriminate against anyone</li>
        <li>collect other users' personal details to use outside ProjecTech</li>
        <li>
          upload malicious code, try to break into the platform, scrape it, or get around its
          limits
        </li>
      </ul>

      <h2>What we are not responsible for</h2>
      <p>
        ProjecTech is provided as it is. We do not check developers' skills, and reviews are the
        opinions of users. We are not responsible for the quality, timing or legality of work
        done through the platform, or for what users say or do. We are not responsible for
        failures of Paystack, M-Pesa, mobile networks, hosting or email providers, although we
        will work to fix problems we can.
      </p>
      <p>
        To the extent the law allows, we are not liable for indirect losses such as lost profit.
        Our total liability to you for any claim about ProjecTech is limited to the fees we
        received from you in the 12 months before the claim. This limit does not apply to money
        we are holding for a project, which we pay out as these terms say. It also does not limit
        liability for fraud, for death or injury caused by negligence, or any right you have
        under Kenyan law that cannot be limited.
      </p>

      <h2>Suspending and closing accounts</h2>
      <p>
        You can close your account at any time by emailing privacy@projectech.dev. We will pay
        out earnings that are free to withdraw, and close the account once any held payment or
        open problem report on your projects is settled.
      </p>
      <p>
        We may suspend or close an account that breaks these terms, puts others at risk, or that
        the law requires us to close. We will tell you why first where we can. If we close your
        account and you did not break these terms, we pay out your balance, except any amount
        under a problem report or investigation. The parts of these terms about money, ownership,
        liability and disputes continue after an account is closed.
      </p>

      <h2>Changes to these terms</h2>
      <p>
        We may change these terms. We will post the new version here with a new date. For changes
        that affect your money or your rights, we will also email you at least 30 days before
        they start. If you keep using ProjecTech after that date, you accept the change. If you
        do not, close your account before then. A project that was paid before a change keeps the
        money rules it started with.
      </p>

      <h2>Law and disputes</h2>
      <p>
        These terms are governed by Kenyan law. If you have a dispute with us, write to
        privacy@projectech.dev and describe it. We will try to settle it within 30 days. If we
        cannot, both sides will go to mediation with a mediator they agree on. If mediation has
        not settled the dispute 30 days after it starts, either side may take it to the courts of
        Nairobi, Kenya. Either side may ask a court for urgent orders at any time.
      </p>

      <h2>Other terms</h2>
      <p>
        These terms and the Privacy Policy are the whole agreement between you and us about
        ProjecTech. If a part is found to be invalid, the rest still applies. If we do not
        enforce a term straight away, we can still enforce it later. We may transfer our rights
        and duties under these terms to a successor business and will tell you if we do. You may
        not transfer your account. We may send you notices by email or on the site.
      </p>

      <h2>Contact</h2>
      <p>
        Shalom Technologies Limited, Nairobi, Kenya. Email privacy@projectech.dev.
      </p>
    </LegalPage>
  );
}
