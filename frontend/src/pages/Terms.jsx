import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

export default function Terms() {
  return (
    <div className="min-h-screen hero-wash">
      <div className="noise-overlay" />
      <div className="relative z-10 max-w-3xl mx-auto px-4 py-10">
        <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-6">
          <ArrowLeft className="h-3.5 w-3.5" /> Back to home
        </Link>

        <h1 className="font-display text-3xl font-bold tracking-tight mb-2">Terms of Service</h1>
        <p className="text-sm text-muted-foreground mb-8">Last updated: July 2026</p>

        <div className="prose prose-sm max-w-none space-y-6 text-sm leading-relaxed text-foreground">
          <section className="space-y-2">
            <h2 className="font-display font-semibold text-lg">1. Acceptance of Terms</h2>
            <p>
              By accessing or using HookForge ("the app"), you agree to be bound by these Terms of Service. If you do not agree to these terms, do not use the app.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="font-display font-semibold text-lg">2. Description of Service</h2>
            <p>
              HookForge is a content creation tool that provides the following services:
            </p>
            <ul className="list-disc pl-5 space-y-1">
              <li>Discovery of trending TikTok video content via the TikTok Content Discovery API</li>
              <li>AI-powered analysis of video hooks (first 2-3 seconds)</li>
              <li>AI face swap technology for inserting your likeness into video frames</li>
              <li>AI video generation from face-swapped reference frames</li>
              <li>Brand profile analysis and customized video prompt generation</li>
            </ul>
          </section>

          <section className="space-y-2">
            <h2 className="font-display font-semibold text-lg">3. User Responsibilities</h2>
            <p>You agree to:</p>
            <ul className="list-disc pl-5 space-y-1">
              <li><strong>Only upload photos of yourself</strong> or photos you have explicit permission to use for face swap purposes</li>
              <li><strong>Not create misleading content</strong> that could deceive others into thinking generated content is real footage of another person</li>
              <li><strong>Not use the app for harassment,</strong> impersonation without consent, or creation of non-consensual intimate imagery</li>
              <li><strong>Comply with all applicable laws</strong> regarding AI-generated content, deepfakes, and digital media in your jurisdiction</li>
              <li><strong>Respect TikTok creators' content</strong> — the app is for inspiration and adaptation, not direct copying or plagiarism</li>
              <li><strong>Not use generated content</strong> in ways that violate TikTok's, Instagram's, or any platform's community guidelines</li>
            </ul>
          </section>

          <section className="space-y-2">
            <h2 className="font-display font-semibold text-lg">4. Content Ownership</h2>
            <ul className="list-disc pl-5 space-y-1">
              <li><strong>Your uploads:</strong> You retain ownership of photos you upload.</li>
              <li><strong>Generated content:</strong> You own the AI-generated face-swapped images and videos created using your photos, subject to the underlying AI models' terms.</li>
              <li><strong>TikTok content:</strong> Videos displayed from TikTok remain the property of their original creators. The app displays this content with proper attribution and linking.</li>
              <li><strong>Brand profiles:</strong> Brand information you provide remains yours.</li>
            </ul>
          </section>

          <section className="space-y-2">
            <h2 className="font-display font-semibold text-lg">5. Prohibited Uses</h2>
            <p>You may NOT use HookForge to:</p>
            <ul className="list-disc pl-5 space-y-1">
              <li>Create non-consensual face swaps of other people</li>
              <li>Generate sexually explicit or violent content</li>
              <li>Impersonate public figures or private individuals for deceptive purposes</li>
              <li>Create content intended to mislead, defraud, or manipulate</li>
              <li>Violate any person's right of publicity, privacy, or intellectual property</li>
              <li>Scrape, redistribute, or commercially exploit TikTok content beyond what the API permits</li>
              <li>Reverse-engineer, modify, or attempt to extract the underlying AI models</li>
            </ul>
          </section>

          <section className="space-y-2">
            <h2 className="font-display font-semibold text-lg">6. Third-Party Services</h2>
            <p>
              The app relies on third-party AI services (OpenRouter, Google Gemini, ByteDance, Alibaba) and the TikTok Content Discovery API. These services have their own terms and may be subject to availability, rate limits, or content policies that affect the app's functionality.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="font-display font-semibold text-lg">7. Disclaimers</h2>
            <ul className="list-disc pl-5 space-y-1">
              <li>The app is provided "as is" without warranties of any kind</li>
              <li>AI-generated content may not always be accurate, appropriate, or of consistent quality</li>
              <li>We do not guarantee the availability of trending video content or AI generation services</li>
              <li>You are solely responsible for how you use generated content</li>
            </ul>
          </section>

          <section className="space-y-2">
            <h2 className="font-display font-semibold text-lg">8. Limitation of Liability</h2>
            <p>
              HookForge shall not be liable for any indirect, incidental, special, or consequential damages arising from your use of the app, including but not limited to damages from generated content, third-party service outages, or data loss.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="font-display font-semibold text-lg">9. Termination</h2>
            <p>
              We reserve the right to suspend or terminate access to the app if these terms are violated. Upon termination, your stored data will be deleted within 30 days.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="font-display font-semibold text-lg">10. Changes to Terms</h2>
            <p>
              We may update these Terms of Service at any time. Continued use of the app after changes constitutes acceptance of the updated terms.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="font-display font-semibold text-lg">11. Contact</h2>
            <p>
              For questions about these Terms of Service, contact us at: <strong>legal@hookforge.app</strong>
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
