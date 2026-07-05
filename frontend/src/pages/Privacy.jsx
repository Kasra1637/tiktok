import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

export default function Privacy() {
  return (
    <div className="min-h-screen hero-wash">
      <div className="noise-overlay" />
      <div className="relative z-10 max-w-3xl mx-auto px-4 py-10">
        <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-6">
          <ArrowLeft className="h-3.5 w-3.5" /> Back to home
        </Link>

        <h1 className="font-display text-3xl font-bold tracking-tight mb-2">Privacy Policy</h1>
        <p className="text-sm text-muted-foreground mb-8">Last updated: July 2026</p>

        <div className="prose prose-sm max-w-none space-y-6 text-sm leading-relaxed text-foreground">
          <section className="space-y-2">
            <h2 className="font-display font-semibold text-lg">1. Overview</h2>
            <p>
              HookForge ("we," "our," or "the app") is a content creation tool that helps creators discover trending video hooks, perform AI-powered face swaps, and generate branded short-form video content. This Privacy Policy explains how we collect, use, and protect information when you use our application.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="font-display font-semibold text-lg">2. Information We Collect</h2>
            <h3 className="font-semibold text-sm">Content You Provide:</h3>
            <ul className="list-disc pl-5 space-y-1">
              <li><strong>Face photos:</strong> Images you upload for face swap processing. These are stored temporarily on our servers for generation purposes.</li>
              <li><strong>Brand information:</strong> Website URLs you submit for brand analysis, and any brand profile data extracted or manually entered.</li>
              <li><strong>TikTok video URLs:</strong> URLs you paste for hook analysis.</li>
            </ul>
            <h3 className="font-semibold text-sm">Automatically Collected:</h3>
            <ul className="list-disc pl-5 space-y-1">
              <li><strong>Usage data:</strong> Pages visited, features used, and generation requests made.</li>
              <li><strong>Browser storage:</strong> Saved face data is stored in your browser's localStorage and never transmitted to our servers unless you initiate a face swap.</li>
            </ul>
            <h3 className="font-semibold text-sm">Third-Party Content:</h3>
            <ul className="list-disc pl-5 space-y-1">
              <li><strong>TikTok videos:</strong> We access publicly available TikTok content via the TikTok Content Discovery API for displaying trending videos within the app. We do not store or redistribute TikTok videos beyond temporary caching for analysis.</li>
            </ul>
          </section>

          <section className="space-y-2">
            <h2 className="font-display font-semibold text-lg">3. How We Use Your Information</h2>
            <ul className="list-disc pl-5 space-y-1">
              <li>To perform AI face swap generation using your uploaded photos</li>
              <li>To analyze viral video hooks and provide structured insights</li>
              <li>To generate branded video content based on your brand profile</li>
              <li>To display trending TikTok content relevant to your selected niche</li>
              <li>To improve the app's functionality and user experience</li>
            </ul>
          </section>

          <section className="space-y-2">
            <h2 className="font-display font-semibold text-lg">4. Third-Party Services</h2>
            <p>We use the following third-party services to provide our functionality:</p>
            <ul className="list-disc pl-5 space-y-1">
              <li><strong>OpenRouter API:</strong> For AI image generation (face swap), video generation, and text analysis. Your images are sent to their API for processing.</li>
              <li><strong>Google Gemini:</strong> For vision-based hook analysis and image generation (via OpenRouter).</li>
              <li><strong>ByteDance Seedance / Alibaba Wan:</strong> For AI video generation (via OpenRouter).</li>
              <li><strong>TikTok Content Discovery API:</strong> For displaying publicly available trending videos within the app.</li>
            </ul>
            <p>Each third-party service has its own privacy policy governing how they handle data sent to them.</p>
          </section>

          <section className="space-y-2">
            <h2 className="font-display font-semibold text-lg">5. Data Storage & Retention</h2>
            <ul className="list-disc pl-5 space-y-1">
              <li><strong>Uploaded photos:</strong> Stored on our servers for the duration needed to complete generation. May be retained for up to 30 days for caching purposes, then deleted.</li>
              <li><strong>Generated content:</strong> Face-swapped images and videos are stored until you delete them or for up to 90 days.</li>
              <li><strong>Brand profiles:</strong> Retained until you manually delete them.</li>
              <li><strong>Analysis data:</strong> Hook analysis results are cached to avoid re-processing the same videos.</li>
              <li><strong>Saved face (localStorage):</strong> Stored only in your browser. We never access this data unless you explicitly trigger a face swap.</li>
            </ul>
          </section>

          <section className="space-y-2">
            <h2 className="font-display font-semibold text-lg">6. Data Security</h2>
            <p>
              We implement industry-standard security measures to protect your data, including encrypted connections (HTTPS), secure server infrastructure, and access controls. However, no method of transmission over the internet is 100% secure.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="font-display font-semibold text-lg">7. Your Rights</h2>
            <p>You have the right to:</p>
            <ul className="list-disc pl-5 space-y-1">
              <li>Delete your uploaded photos and generated content at any time</li>
              <li>Clear your saved face from browser storage</li>
              <li>Delete your brand profile</li>
              <li>Request deletion of all your data by contacting us</li>
            </ul>
          </section>

          <section className="space-y-2">
            <h2 className="font-display font-semibold text-lg">8. TikTok Content</h2>
            <p>
              Videos displayed in the app are publicly available TikTok content accessed through official API channels. We display video thumbnails and metadata with attribution, and always link back to the original content on TikTok. We do not claim ownership of any TikTok creator's content.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="font-display font-semibold text-lg">9. Responsible Use</h2>
            <p>
              Our face swap technology is designed for creative, professional, and marketing purposes. Users must not use this tool to create non-consensual, misleading, or harmful content. We prohibit the creation of content that impersonates others without permission or that could be used to deceive or harass.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="font-display font-semibold text-lg">10. Changes to This Policy</h2>
            <p>
              We may update this Privacy Policy from time to time. Any changes will be reflected on this page with an updated "Last updated" date.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="font-display font-semibold text-lg">11. Contact</h2>
            <p>
              For questions about this Privacy Policy or to request data deletion, contact us at: <strong>privacy@hookforge.app</strong>
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
