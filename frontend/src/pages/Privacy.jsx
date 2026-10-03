import LegalPage, { LegalSection, LegalSubheading, LegalList, LegalItem } from "../components/LegalPage";

export default function Privacy() {
  return (
    <LegalPage title="Privacy Policy" updated="September 2026">
      <LegalSection number={1} title="Overview">
        <p>
          HookForge ("we," "our," or "the app") is an internal template-based tool that helps mobile app founders research reusable hook mechanics and generate short-form promotional videos from approved App Profiles. Exact-match video recreation is disabled. This Privacy Policy explains how we collect, use, and protect information when you use our application.
        </p>
      </LegalSection>

      <LegalSection number={2} title="Information We Collect">
        <LegalSubheading>Content You Provide:</LegalSubheading>
        <LegalList>
          <LegalItem><strong>App assets:</strong> The character reference photograph you upload for a specific App Profile. Upload only a photograph you have the right to use.</LegalItem>
          <LegalItem><strong>Brand information:</strong> Website, App Store, Google Play, and support URLs you submit for research, and any App Profile data extracted or manually entered.</LegalItem>
          <LegalItem><strong>TikTok video URLs:</strong> URLs you paste for hook analysis.</LegalItem>
        </LegalList>
        <LegalSubheading>Automatically Collected:</LegalSubheading>
        <LegalList>
          <LegalItem><strong>Usage data:</strong> Pages visited, features used, and generation requests made.</LegalItem>
        </LegalList>
        <LegalSubheading>Third-Party Content:</LegalSubheading>
        <LegalList>
          <LegalItem><strong>TikTok videos:</strong> We access publicly available TikTok content for trend research scans that abstract reusable mechanics. We do not store or redistribute TikTok videos beyond temporary caching for analysis.</LegalItem>
        </LegalList>
      </LegalSection>

      <LegalSection number={3} title="How We Use Your Information">
        <LegalList>
          <LegalItem>To research mobile apps and draft reviewable App Profiles</LegalItem>
          <LegalItem>To analyze video hooks and abstract reusable template mechanics</LegalItem>
          <LegalItem>To generate template-based promotional videos from approved profiles and authorized assets</LegalItem>
          <LegalItem>To display trend research results relevant to your selected niche</LegalItem>
          <LegalItem>To improve the app's functionality and user experience</LegalItem>
        </LegalList>
      </LegalSection>

      <LegalSection number={4} title="Third-Party Services">
        <p>We use the following third-party services to provide our functionality:</p>
        <LegalList>
          <LegalItem><strong>OpenRouter API:</strong> For text analysis, hook analysis, and video generation. App assets and prompts needed for those operations are sent to their API for processing.</LegalItem>
          <LegalItem><strong>Google Gemini:</strong> For vision-based hook analysis and text generation (via OpenRouter).</LegalItem>
          <LegalItem><strong>TikTok Content Discovery API:</strong> For trend research scans of publicly available content.</LegalItem>
          <LegalItem><strong>Cloudflare R2 and Turso:</strong> For durable video and application storage where configured.</LegalItem>
        </LegalList>
        <p>Each third-party service has its own privacy policy governing how they handle data sent to them.</p>
      </LegalSection>

      <LegalSection number={5} title="Data Storage & Retention">
        <LegalList>
          <LegalItem><strong>Uploaded assets:</strong> Retained until you archive or delete them.</LegalItem>
          <LegalItem><strong>Generated content:</strong> Template-based videos are stored until you delete them or for up to 90 days.</LegalItem>
          <LegalItem><strong>App and brand profiles:</strong> Retained until you manually delete them.</LegalItem>
          <LegalItem><strong>Analysis data:</strong> Hook analysis results are cached to avoid re-processing the same videos.</LegalItem>
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
          <LegalItem>Delete your uploaded assets and generated content at any time</LegalItem>
          <LegalItem>Delete your App Profile or brand profile</LegalItem>
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
          HookForge is designed for lawful app promotion using approved product facts and authorized assets. Users must not use this tool to create non-consensual, misleading, infringing, or harmful content. We prohibit impersonation, deceptive product claims, fake reviews or testimonials, fabricated app interfaces or pricing, and use of copyrighted audio or likenesses without permission.
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
