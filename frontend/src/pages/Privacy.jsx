import LegalPage, { LegalSection, LegalSubheading, LegalList, LegalItem } from "../components/LegalPage";

export default function Privacy() {
  return (
    <LegalPage title="Privacy Policy" updated="July 2026">
      <LegalSection number={1} title="Overview">
        <p>
          HookForge ("we," "our," or "the app") is a content creation tool that helps creators discover trending video hooks, perform AI-powered face swaps, and generate branded short-form video content. This Privacy Policy explains how we collect, use, and protect information when you use our application.
        </p>
      </LegalSection>

      <LegalSection number={2} title="Information We Collect">
        <LegalSubheading>Content You Provide:</LegalSubheading>
        <LegalList>
          <LegalItem><strong>Face photos:</strong> Images you upload for face swap processing. These are stored temporarily on our servers for generation purposes.</LegalItem>
          <LegalItem><strong>Brand information:</strong> Website URLs you submit for brand analysis, and any brand profile data extracted or manually entered.</LegalItem>
          <LegalItem><strong>TikTok video URLs:</strong> URLs you paste for hook analysis.</LegalItem>
        </LegalList>
        <LegalSubheading>Automatically Collected:</LegalSubheading>
        <LegalList>
          <LegalItem><strong>Usage data:</strong> Pages visited, features used, and generation requests made.</LegalItem>
          <LegalItem><strong>Browser storage:</strong> Saved face data is stored in your browser's localStorage and never transmitted to our servers unless you initiate a face swap.</LegalItem>
        </LegalList>
        <LegalSubheading>Third-Party Content:</LegalSubheading>
        <LegalList>
          <LegalItem><strong>TikTok videos:</strong> We access publicly available TikTok content via the TikTok Content Discovery API for displaying trending videos within the app. We do not store or redistribute TikTok videos beyond temporary caching for analysis.</LegalItem>
        </LegalList>
      </LegalSection>

      <LegalSection number={3} title="How We Use Your Information">
        <LegalList>
          <LegalItem>To perform AI face swap generation using your uploaded photos</LegalItem>
          <LegalItem>To analyze viral video hooks and provide structured insights</LegalItem>
          <LegalItem>To generate branded video content based on your brand profile</LegalItem>
          <LegalItem>To display trending TikTok content relevant to your selected niche</LegalItem>
          <LegalItem>To improve the app's functionality and user experience</LegalItem>
        </LegalList>
      </LegalSection>

      <LegalSection number={4} title="Third-Party Services">
        <p>We use the following third-party services to provide our functionality:</p>
        <LegalList>
          <LegalItem><strong>OpenRouter API:</strong> For AI image generation (face swap), video generation, and text analysis. Your images are sent to their API for processing.</LegalItem>
          <LegalItem><strong>Google Gemini:</strong> For vision-based hook analysis and image generation (via OpenRouter).</LegalItem>
          <LegalItem><strong>Runway Aleph 2.0:</strong> For in-context video editing that replaces facial identity on the original hook footage (via OpenRouter). Falls back to MiniMax H3 for customized or generated hooks.</LegalItem>
          <LegalItem><strong>TikTok Content Discovery API:</strong> For displaying publicly available trending videos within the app.</LegalItem>
        </LegalList>
        <p>Each third-party service has its own privacy policy governing how they handle data sent to them.</p>
      </LegalSection>

      <LegalSection number={5} title="Data Storage & Retention">
        <LegalList>
          <LegalItem><strong>Uploaded photos:</strong> Stored on our servers for the duration needed to complete generation. May be retained for up to 30 days for caching purposes, then deleted.</LegalItem>
          <LegalItem><strong>Generated content:</strong> Face-swapped images and videos are stored until you delete them or for up to 90 days.</LegalItem>
          <LegalItem><strong>Brand profiles:</strong> Retained until you manually delete them.</LegalItem>
          <LegalItem><strong>Analysis data:</strong> Hook analysis results are cached to avoid re-processing the same videos.</LegalItem>
          <LegalItem><strong>Saved face (localStorage):</strong> Stored only in your browser. We never access this data unless you explicitly trigger a face swap.</LegalItem>
        </LegalList>
      </LegalSection>

      <LegalSection number={6} title="Data Security">
        <p>
          We implement industry-standard security measures to protect your data, including encrypted connections (HTTPS), secure server infrastructure, and access controls. However, no method of transmission over the internet is 100% secure.
        </p>
      </LegalSection>

      <LegalSection number={7} title="Your Rights">
        <p>You have the right to:</p>
        <LegalList>
          <LegalItem>Delete your uploaded photos and generated content at any time</LegalItem>
          <LegalItem>Clear your saved face from browser storage</LegalItem>
          <LegalItem>Delete your brand profile</LegalItem>
          <LegalItem>Request deletion of all your data by contacting us</LegalItem>
        </LegalList>
      </LegalSection>

      <LegalSection number={8} title="TikTok Content">
        <p>
          Videos displayed in the app are publicly available TikTok content accessed through official API channels. We display video thumbnails and metadata with attribution, and always link back to the original content on TikTok. We do not claim ownership of any TikTok creator's content.
        </p>
      </LegalSection>

      <LegalSection number={9} title="Responsible Use">
        <p>
          Our face swap technology is designed for creative, professional, and marketing purposes. Users must not use this tool to create non-consensual, misleading, or harmful content. We prohibit the creation of content that impersonates others without permission or that could be used to deceive or harass.
        </p>
      </LegalSection>

      <LegalSection number={10} title="Changes to This Policy">
        <p>
          We may update this Privacy Policy from time to time. Any changes will be reflected on this page with an updated "Last updated" date.
        </p>
      </LegalSection>

      <LegalSection number={11} title="Contact">
        <p>
          For questions about this Privacy Policy or to request data deletion, contact us at: <strong>privacy@hookforge.app</strong>
        </p>
      </LegalSection>
    </LegalPage>
  );
}
