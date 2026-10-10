import LegalPage, { LegalSection, LegalList, LegalItem } from "../components/LegalPage";

export default function Terms() {
  return (
    <LegalPage title="Terms of Service" updated="September 2026">
      <LegalSection number={1} title="Acceptance of Terms">
        <p>
          By accessing or using HookForge ("the app"), you agree to be bound by these Terms of Service. If you do not agree to these terms, do not use the app.
        </p>
      </LegalSection>

      <LegalSection number={2} title="Description of Service">
        <p>HookForge is an internal template-based video tool that provides the following services:</p>
        <LegalList>
          <LegalItem>Trend research scans of public TikTok content for reusable mechanics</LegalItem>
          <LegalItem>AI-powered analysis of video hooks and abstraction of reusable mechanics</LegalItem>
          <LegalItem>Mobile App Profiles, content angles, and hook-template recommendations</LegalItem>
          <LegalItem>Template-based promotional video generation from approved profiles and authorized assets</LegalItem>
          <LegalItem>Manual video download and performance-note tracking</LegalItem>
        </LegalList>
        <p>Exact-match video recreation is disabled. The app does not automatically publish content.</p>
      </LegalSection>

      <LegalSection number={3} title="User Responsibilities">
        <p>You agree to:</p>
        <LegalList>
          <LegalItem><strong>Only upload assets</strong> that you own or have explicit permission to use for app promotion</LegalItem>
          <LegalItem><strong>Use approved product facts</strong> and avoid fabricating features, pricing, reviews, testimonials, or guaranteed outcomes</LegalItem>
          <LegalItem><strong>Not create misleading content</strong> that could deceive others about a product, person, or result</LegalItem>
          <LegalItem><strong>Not use the app for harassment,</strong> impersonate others without consent, or create non-consensual intimate imagery</LegalItem>
          <LegalItem><strong>Comply with all applicable laws</strong> that govern AI-generated content and digital media in your jurisdiction</LegalItem>
          <LegalItem><strong>Respect TikTok creators' content</strong> — the app is for inspiration and reusable mechanics, not direct copying or plagiarism</LegalItem>
          <LegalItem><strong>Not use generated content</strong> in a way that violates TikTok's, Instagram's, or any other platform's community guidelines</LegalItem>
        </LegalList>
      </LegalSection>

      <LegalSection number={4} title="Content Ownership">
        <LegalList>
          <LegalItem><strong>Your uploads:</strong> You retain ownership of assets you upload.</LegalItem>
          <LegalItem><strong>Generated content:</strong> You own the template-based promotional videos generated from your approved profiles and authorized assets, subject to the underlying AI models' terms.</LegalItem>
          <LegalItem><strong>TikTok content:</strong> Videos displayed from TikTok remain the property of their original creators. The app displays this content with proper attribution and linking.</LegalItem>
          <LegalItem><strong>App and brand profiles:</strong> Profile information you provide remains yours.</LegalItem>
        </LegalList>
      </LegalSection>

      <LegalSection number={5} title="Prohibited Uses">
        <p>You may NOT use HookForge to:</p>
        <LegalList>
          <LegalItem>Recreate another creator's exact identity, performance, gestures, voice, or copyrighted audio</LegalItem>
          <LegalItem>Create non-consensual face swaps or impersonations of other people</LegalItem>
          <LegalItem>Generate sexually explicit or violent content</LegalItem>
          <LegalItem>Impersonate public figures or private individuals for deceptive purposes</LegalItem>
          <LegalItem>Create content intended to mislead, defraud, or manipulate</LegalItem>
          <LegalItem>Violate any person's right of publicity, privacy, or intellectual property</LegalItem>
          <LegalItem>Scrape, redistribute, or commercially exploit TikTok content beyond what the API permits</LegalItem>
          <LegalItem>Reverse-engineer, modify, or attempt to extract the underlying AI models</LegalItem>
        </LegalList>
      </LegalSection>

      <LegalSection number={6} title="Third-Party Services">
        <p>
          The app relies on third-party AI services (OpenRouter and Google Gemini), configurable video-generation providers, and the TikTok Content Discovery API. These services have their own terms and may be subject to availability, rate limits, or content policies that affect the app's functionality.
        </p>
      </LegalSection>

      <LegalSection number={7} title="Disclaimers">
        <LegalList>
          <LegalItem>The app is provided "as is" without warranties of any kind</LegalItem>
          <LegalItem>AI-generated content may not always be accurate, appropriate, or of consistent quality</LegalItem>
          <LegalItem>We do not guarantee the availability of trending video content or AI generation services</LegalItem>
          <LegalItem>You are solely responsible for how you use generated content</LegalItem>
        </LegalList>
      </LegalSection>

      <LegalSection number={8} title="Limitation of Liability">
        <p>
          HookForge shall not be liable for any indirect, incidental, special, or consequential damages arising from your use of the app, including but not limited to damages from generated content, third-party service outages, or data loss.
        </p>
      </LegalSection>

      <LegalSection number={9} title="Termination">
        <p>
          We reserve the right to suspend or terminate access to the app if these terms are violated. Upon termination, your stored data will be deleted within 30 days.
        </p>
      </LegalSection>

      <LegalSection number={10} title="Changes to Terms">
        <p>
          We may update these Terms of Service at any time. Continued use of the app after changes constitutes acceptance of the updated terms.
        </p>
      </LegalSection>

      <LegalSection number={11} title="Contact">
        <p>
          For questions about these Terms of Service, contact us at: <strong>legal@hookforge.app</strong>
        </p>
      </LegalSection>
    </LegalPage>
  );
}
