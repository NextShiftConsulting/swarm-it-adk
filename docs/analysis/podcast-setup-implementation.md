# Podcast Setup Implementation: Swarm-It by Next Shift Consulting

**Date**: March 12, 2026
**Objective**: Convert NSC blog to podcast format with automated audio generation and iTunes-compliant RSS feed
**Result**: Fully functional podcast RSS feed with 14 episodes, S3 storage, and iTunes metadata

---

## Executive Summary

Successfully implemented a complete blog-to-podcast pipeline for Next Shift Consulting's content, branded as "Swarm-It by Next Shift Consulting". The system automatically converts blog posts to audio using AWS Polly, stores MP3 files in S3, and generates an iTunes-compliant podcast RSS feed.

**Key Metrics:**
- 57 blog posts with audio generated (14 currently published)
- Audio files: 2.3MB - 3.9MB per episode
- Storage: AWS S3 (dsai-2025-asu bucket)
- Cost per post: ~$0.40 (AWS Polly Neural voices)
- Build time impact: ~2 seconds (skips existing S3 files)

---

## Problem Statement

### Initial Challenge

NSC had a rich blog with technical AI content but no audio distribution channel. Requirements:

1. **Audio Generation**: Convert 57 blog posts to professional audio
2. **Cost Optimization**: Avoid regenerating audio on every Netlify build (~$18/build)
3. **RSS Feed**: iTunes-compliant podcast RSS with proper metadata
4. **Scalability**: Automated pipeline for future posts
5. **Storage**: Persistent audio storage outside of git repository

### Technical Constraints

- Gatsby static site generator (build-time RSS generation)
- AWS Polly 3,000 character limit per API call
- Netlify build time limits
- iTunes podcast namespace requirements
- S3 public access configuration

---

## Architecture Overview

```
Blog Post (MDX)
    ↓
Audio Generation Script (scripts/generate-audio.js)
    ↓
AWS Polly (Text-to-Speech)
    ↓
S3 Upload (dsai-2025-asu/audio/*.mp3)
    ↓
Manifest Update (static/audio/manifest.json)
    ↓
Gatsby Build (RSS Feed Generation)
    ↓
RSS Feed with Audio Enclosures
    ↓
FeedBurner (Podcast Distribution)
    ↓
iTunes, Spotify, etc.
```

---

## Implementation Details

### 1. Audio Generation System

**File**: `scripts/generate-audio.js`

**Key Features:**

- **S3-First Check**: Always checks S3 before generating audio
- **Text Chunking**: Handles AWS Polly's 3,000 character limit with intelligent sentence/word splitting
- **Manifest Tracking**: JSON file tracks all generated audio with S3 URLs and metadata
- **Error Recovery**: Validates chunks and forces hard splits if needed

**Critical S3 Check Logic:**

```javascript
if (!options.all) {
  // Always check S3 first if we have a client
  if (s3Client) {
    const s3Key = `audio/${postData.slug}.mp3`;
    const s3Check = await checkS3FileExists(s3Client, s3Bucket, s3Key);
    if (s3Check.exists) {
      console.log(`⏭️  Skipping ${postData.slug} (already in S3)`);
      skippedCount++;

      // Update manifest with S3 info
      if (!manifest.generated[postData.slug]) {
        manifest.generated[postData.slug] = {
          title: postData.title,
          audioFile: `${postData.slug}.mp3`,
          audioSize: s3Check.size,
          s3Url: `https://${s3Bucket}.s3.amazonaws.com/${s3Key}`,
          s3Key: s3Key,
          generatedAt: new Date().toISOString(),
          service: 'aws',
          wordCount: postData.wordCount,
        };
      }
      continue;
    }
  }
}
```

**Text Chunking with Validation:**

```javascript
function splitTextIntoChunks(text, maxLength = 2500) {
  const chunks = [];
  const sentences = text.match(/[^.!?]+[.!?]+/g) || [text];

  let currentChunk = '';

  for (const sentence of sentences) {
    if ((currentChunk + sentence).length > maxLength) {
      if (currentChunk) {
        chunks.push(currentChunk.trim());
        currentChunk = '';
      }

      // If sentence itself is too long, split by words
      if (sentence.length > maxLength) {
        const words = sentence.split(/\s+/);
        let wordChunk = '';

        for (const word of words) {
          if ((wordChunk + ' ' + word).length > maxLength) {
            if (wordChunk) {
              chunks.push(wordChunk.trim());
              wordChunk = word;
            } else {
              // Single word too long, hard split
              chunks.push(word.substring(0, maxLength).trim());
              wordChunk = word.substring(maxLength);
            }
          } else {
            wordChunk += (wordChunk ? ' ' : '') + word;
          }
        }

        if (wordChunk) {
          currentChunk = wordChunk;
        }
      } else {
        currentChunk = sentence;
      }
    } else {
      currentChunk += sentence;
    }
  }

  if (currentChunk) {
    chunks.push(currentChunk.trim());
  }

  // Validation step with hard character limits
  const validatedChunks = [];
  for (const chunk of chunks) {
    if (chunk.length <= maxLength) {
      validatedChunks.push(chunk);
    } else {
      console.log(`   ⚠️  Chunk too long (${chunk.length} chars), forcing hard split`);
      let remaining = chunk;
      while (remaining.length > 0) {
        validatedChunks.push(remaining.substring(0, maxLength).trim());
        remaining = remaining.substring(maxLength);
      }
    }
  }

  return validatedChunks;
}
```

### 2. Manifest Structure

**File**: `static/audio/manifest.json`

```json
{
  "generated": {
    "rsn-collapse-when-decomposition-fails": {
      "title": "RSN Collapse: When Your Quality Signal Becomes Noise",
      "audioFile": "rsn-collapse-when-decomposition-fails.mp3",
      "audioSize": 2622084,
      "s3Url": "https://dsai-2025-asu.s3.amazonaws.com/audio/rsn-collapse-when-decomposition-fails.mp3",
      "s3Key": "audio/rsn-collapse-when-decomposition-fails.mp3",
      "generatedAt": "2026-03-12T19:10:36.669Z",
      "service": "aws",
      "wordCount": 981
    }
  },
  "lastUpdated": "2026-03-12T19:10:36.685Z",
  "version": "1.0"
}
```

### 3. RSS Feed Configuration

**File**: `gatsby-config.mjs`

**Problem Discovered:**

Initial implementation was missing iTunes podcast namespace and channel-level metadata. RSS feed had:
- ❌ No `xmlns:itunes` namespace declaration
- ❌ No channel-level iTunes tags (author, owner, category, image)
- ❌ Enclosure `length="0"` instead of actual file sizes

**Root Causes:**

1. **Missing iTunes Namespace**: `gatsby-plugin-feed` requires explicit namespace declaration
2. **Enclosure Length Issue**: Direct `enclosure` field wasn't being serialized correctly; needed `custom_elements` with `_attr` format
3. **No Channel Metadata**: iTunes requires podcast-level metadata separate from episode metadata

**Solution:**

```javascript
{
  resolve: `gatsby-plugin-feed`,
  options: {
    feeds: [{
      output: "/rss.xml",
      title: "Swarm-It by Next Shift Consulting",
      description: "Author of RSCT Representation-Solver Compatibility Theory talks about AI reasoning, context quality, solver fit, and the future of intelligent systems",
      feed_url: "https://nextshiftconsulting.com/rss.xml",
      site_url: "https://nextshiftconsulting.com",
      language: "en",

      // CRITICAL: iTunes namespace
      custom_namespaces: {
        itunes: "http://www.itunes.com/dtds/podcast-1.0.dtd",
      },

      // CRITICAL: Channel-level iTunes tags
      custom_elements: [
        { "itunes:author": "Rudy Martin" },
        { "itunes:summary": "Author of RSCT Representation-Solver Compatibility Theory talks about AI reasoning, context quality, solver fit, and the future of intelligent systems" },
        { "itunes:subtitle": "AI reasoning, context quality, and intelligent systems" },
        { "itunes:keywords": "Context Engineering, Enterprise AI, AI consulting, Artificial intelligence, Machine learning, AI engineering, Multi-agent systems, Research discovery, Context quality, AI safety, RAG Automation, Data science" },
        { "itunes:owner": [
          { "itunes:name": "Rudy Martin" },
          { "itunes:email": "inquiries@nextshiftconsulting.com" },
        ]},
        { "itunes:explicit": "no" },
        { "itunes:category": [
          { _attr: { text: "Technology" }},
          { "itunes:category": { _attr: { text: "Tech News" }}},
        ]},
        { "itunes:image": { _attr: { href: "https://nextshiftconsulting.com/img/icons/NSC-3000.png" }}},
        { "itunes:type": "episodic" },
      ],
    }],
  },
}
```

**Episode-Level Enclosure (via custom_elements):**

```javascript
// Build custom elements
const customElements = [
  { "content:encoded": fullContent },
]

// CRITICAL: Add enclosure via custom_elements with _attr
if (audioEnclosure) {
  customElements.push({
    enclosure: {
      _attr: {
        url: audioEnclosure.url,
        length: parseInt(audioEnclosure.length, 10),  // Must be integer
        type: audioEnclosure.type,
      }
    }
  })
}

// Add iTunes episode metadata
if (audioEnclosure) {
  customElements.push({ "itunes:duration": audioData.duration || "00:00:00" })
  customElements.push({ "itunes:explicit": "no" })
  customElements.push({ "itunes:episodeType": "full" })
  customElements.push({ "itunes:author": "Rudy Martin" })
  if (imageUrl) {
    customElements.push({ "itunes:image": { _attr: { href: imageUrl } } })
  }
}

return {
  title: node.frontmatter.title,
  description: node.frontmatter.description || node.excerpt,
  date: node.frontmatter.date,
  url: url,
  guid: url,
  custom_elements: customElements,
}
```

### 4. iTunes Podcast Requirements

Based on Apple Podcasts documentation and industry best practices:

**Required Channel-Level Tags:**

- `<title>` — Podcast name
- `<link>` — Website URL
- `<language>` — Language code (en)
- `<itunes:author>` — Creator name
- `<description>` — Show summary
- `<itunes:image>` — Artwork URL (1400x1400 to 3000x3000 pixels, JPEG/PNG)
- `<itunes:category>` — Genre classification
- `<itunes:explicit>` — Content rating (yes/no/clean)
- `<itunes:owner>` — Contact info (name + email)

**Required Episode-Level Tags:**

- `<title>` — Episode name
- `<description>` — Episode details
- `<enclosure>` — Media file with `url`, `length` (bytes as integer), `type` attributes
- `<guid>` — Unique identifier (never changes)
- `<pubDate>` — Release timestamp (RFC 2822 format)
- `<itunes:duration>` — Length (HH:MM:SS or seconds)
- `<itunes:explicit>` — Content rating
- `<itunes:episodeType>` — "full", "trailer", or "bonus"

**Best Practices:**

- Square artwork between 1400×1400 and 3000×3000 pixels
- UTF-8 encoding for all text
- ASCII-only filenames and URLs (a-z, A-Z, 0-9)
- Validate feed before submission to iTunes
- Use `itunes:season` and `itunes:episode` tags instead of embedding numbers in titles
- Support HTTP HEAD requests and byte-range requests for streaming

**Sources:**
- [Podcast RSS feed requirements - Apple Podcasts for Creators](https://podcasters.apple.com/support/823-podcast-requirements)
- [RSS Feed Sample - Apple Help](https://help.apple.com/itc/podcasts_connect/en.lproj/itcbaf351599.html)
- [Podcast RSS Feed Guide 2026](https://rssvalidator.app/podcast-rss-guide)

### 5. S3 Storage Configuration

**Bucket**: `dsai-2025-asu`
**Region**: `us-east-1`

**Structure:**

```
s3://dsai-2025-asu/
└── audio/
    ├── rsn-collapse-when-decomposition-fails.mp3 (2.6MB)
    ├── the-same-image-over-and-over.mp3 (2.5MB)
    ├── when-models-forget-to-be-curious.mp3 (2.7MB)
    └── ... (57 total files)
```

**Access Configuration:**

- Public read access via bucket policy
- CloudFront distribution (optional for CDN)
- CORS enabled for web playback

**Environment Variables:**

```bash
# .env.development (example format)
# AWS credentials stored securely in environment
CLIENT_AWS_REGION=us-east-1
CLIENT_S3_BUCKET=dsai-2025-asu
AWS_POLLY_VOICE=Matthew
# Note: Actual credentials configured via AWS CLI or environment
```

**Netlify Build Environment:**

Same environment variables configured in Netlify dashboard under Site Settings → Environment variables.

---

## Build Pipeline Integration

### Build Command

```json
{
  "scripts": {
    "deploy:netlify": "yarn clean && node scripts/generate-audio.js && NODE_ENV=production gatsby build && node scripts/purge-cache-safe.js"
  }
}
```

### Build Sequence

1. **Clean**: `gatsby clean` - removes .cache and public directories
2. **Audio Generation**: Checks S3, skips existing files, generates only new posts
3. **Gatsby Build**: Generates static site + RSS feed with audio enclosures
4. **Cache Purge**: Cloudflare cache invalidation for immediate RSS feed updates

### Performance

**First Build** (all audio):
- Duration: ~5-10 minutes additional build time
- Cost: ~$5.60 for 14 posts (AWS Polly)

**Subsequent Builds** (S3 check):
- Duration: ~2 seconds additional build time
- Skipped: 57/57 files (already in S3)
- Cost: $0 (only S3 API calls)

---

## Cost Analysis

### AWS Polly Pricing

- **Neural Voices**: $16 per 1 million characters
- **Average Post**: ~25,000 characters = $0.40 per post
- **Initial 57 Posts**: ~$22.80 one-time cost
- **Monthly (4 new posts)**: ~$1.60/month

### S3 Storage Pricing

- **Storage**: $0.023 per GB/month
- **Current Usage**: ~150 MB (57 files) = $0.003/month
- **Bandwidth**: First 100 GB/month free
- **Effectively**: Free for this use case

### Total Cost of Ownership

- **Initial Setup**: ~$23 (one-time)
- **Monthly Ongoing**: ~$1.60/month for new posts
- **Storage**: Negligible (~$0.003/month)

---

## Issues Encountered & Resolutions

### Issue 1: RSS Feed Empty (0 Items)

**Problem**: RSS feed had no items despite 14 published blog posts.

**Root Cause**: GraphQL query had `limit: 20` which grabbed the 20 newest posts BEFORE filtering out future posts. Since the 20 newest were all future-dated, the feed ended up empty after date filtering.

**Solution**: Remove `limit: 20` from GraphQL query, apply `.slice(0, 20)` AFTER date filtering in serialize function.

```javascript
const filteredNodes = allMdx.nodes
  .filter(node => {
    const postDate = new Date(node.frontmatter.date)
    return postDate <= today
  })
  .slice(0, 20) // Limit AFTER filtering
```

### Issue 2: Audio Regeneration on Every Build

**Problem**: Script regenerated all 57 audio files on every build, costing ~$18-20 in AWS Polly charges.

**Root Cause**: Script only checked S3 if the post existed in manifest. Since manifest was committed empty to git, every build regenerated everything.

**Solution**: Always check S3 first before generating, regardless of manifest state.

### Issue 3: AWS Polly "Maximum Text Length Exceeded"

**Problem**: 10 posts failed with "Maximum text length has been exceeded" error even with chunking.

**Root Cause**: Individual chunks still exceeded 3,000 character limit after sentence-based splitting.

**Solution**: Added validation step with word-boundary splitting and hard character limits (shown in implementation above).

### Issue 4: RSS Feed Audio Enclosure Length = 0

**Problem**: All 14 enclosures showed `length="0"` instead of actual file sizes.

**Root Cause**: `gatsby-plugin-feed` wasn't properly handling the direct `enclosure` field. The `audioSize` value was being lost during RSS generation.

**Solution**: Move enclosure to `custom_elements` with `_attr` format and explicit `parseInt()`:

```javascript
customElements.push({
  enclosure: {
    _attr: {
      url: audioEnclosure.url,
      length: parseInt(audioData.audioSize, 10),  // CRITICAL
      type: audioEnclosure.type,
    }
  }
})
```

### Issue 5: Missing iTunes Namespace

**Problem**: RSS feed had episode-level iTunes tags but no namespace declaration and no channel-level metadata.

**Root Cause**: `gatsby-plugin-feed` requires explicit `custom_namespaces` configuration and `custom_elements` for channel-level tags.

**Solution**: Added `custom_namespaces` and channel-level `custom_elements` (shown in RSS configuration above).

---

## Final RSS Feed Output

**URL**: `https://nextshiftconsulting.com/rss.xml`

**Sample Structure:**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:dc="http://purl.org/dc/elements/1.1/"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:atom="http://www.w3.org/2005/Atom"
     version="2.0">
  <channel>
    <title>Swarm-It by Next Shift Consulting</title>
    <description>Author of RSCT Representation-Solver Compatibility Theory talks about AI reasoning, context quality, solver fit, and the future of intelligent systems</description>
    <link>https://nextshiftconsulting.com</link>
    <language>en</language>
    <itunes:author>Rudy Martin</itunes:author>
    <itunes:summary>Author of RSCT Representation-Solver Compatibility Theory talks about AI reasoning, context quality, solver fit, and the future of intelligent systems</itunes:summary>
    <itunes:subtitle>AI reasoning, context quality, and intelligent systems</itunes:subtitle>
    <itunes:keywords>Context Engineering, Enterprise AI, AI consulting, Artificial intelligence, Machine learning, AI engineering, Multi-agent systems, Research discovery, Context quality, AI safety, RAG Automation, Data science</itunes:keywords>
    <itunes:owner>
      <itunes:name>Rudy Martin</itunes:name>
      <itunes:email>inquiries@nextshiftconsulting.com</itunes:email>
    </itunes:owner>
    <itunes:explicit>no</itunes:explicit>
    <itunes:category text="Technology">
      <itunes:category text="Tech News"/>
    </itunes:category>
    <itunes:image href="https://nextshiftconsulting.com/img/icons/NSC-3000.png"/>
    <itunes:type>episodic</itunes:type>

    <item>
      <title>RSN Collapse: When Your Quality Signal Becomes Noise</title>
      <description>If Relevant, Superfluous, and Noise all look the same, you can't measure context quality. RSN collapse is the failure mode that breaks the measurement itself.</description>
      <link>https://nextshiftconsulting.com/blog/rsn-collapse-when-decomposition-fails/</link>
      <guid>https://nextshiftconsulting.com/blog/rsn-collapse-when-decomposition-fails/</guid>
      <pubDate>Tue, 10 Mar 2026 00:00:00 GMT</pubDate>
      <enclosure url="https://dsai-2025-asu.s3.amazonaws.com/audio/rsn-collapse-when-decomposition-fails.mp3" length="2622084" type="audio/mpeg"/>
      <itunes:duration>00:00:00</itunes:duration>
      <itunes:explicit>no</itunes:explicit>
      <itunes:episodeType>full</itunes:episodeType>
      <itunes:author>Rudy Martin</itunes:author>
      <itunes:image href="https://nextshiftconsulting.com/img/blog/rsn-collapse.png"/>
    </item>

    <!-- ... 13 more episodes ... -->
  </channel>
</rss>
```

**Validation Results:**

- ✅ 14 published episodes with audio
- ✅ All enclosures have correct file sizes (2.3MB - 3.9MB)
- ✅ All audio files served from dsai-2025-asu S3 bucket
- ✅ iTunes namespace and all required tags present
- ✅ Valid RSS 2.0 + iTunes podcast format

---

## FeedBurner Configuration

**Feed URL**: `http://feeds.feedburner.com/nextshiftconsulting/blog`
**Source**: `https://nextshiftconsulting.com/rss.xml`

**SmartCast Settings:**

Once FeedBurner cache refreshes (every 30 minutes), configure:

1. **Podcast Information**
   - Title: Swarm-It by Next Shift Consulting
   - Subtitle: AI reasoning, context quality, and intelligent systems
   - Author: Rudy Martin
   - Summary: Author of RSCT Representation-Solver Compatibility Theory talks about AI reasoning, context quality, solver fit, and the future of intelligent systems
   - Keywords: Context Engineering, Enterprise AI, AI consulting, Artificial intelligence, Machine learning, AI engineering, Multi-agent systems, Research discovery, Context quality, AI safety, RAG Automation, Data science

2. **Podcast Image**
   - URL: `https://nextshiftconsulting.com/img/icons/NSC-3000.png`
   - Size: 3000×3000 pixels
   - Format: PNG

3. **Category**
   - Primary: Technology
   - Subcategory: Tech News

4. **Content Rating**
   - Explicit: No

---

## Next Steps: Podcast Distribution

### 1. Submit to Apple Podcasts

- URL: https://podcasts.apple.com/podcast-connect
- Submit FeedBurner URL: `http://feeds.feedburner.com/nextshiftconsulting/blog`
- Wait for review (typically 1-3 days)

### 2. Submit to Spotify

- URL: https://podcasters.spotify.com
- Submit RSS feed URL
- Verify ownership via email confirmation

### 3. Submit to Google Podcasts

- URL: https://podcastsmanager.google.com
- Submit RSS feed URL
- Auto-indexed from RSS feed

### 4. Other Directories

- **Stitcher**: https://www.stitcher.com/content-providers
- **Amazon Music**: https://podcasters.amazon.com
- **iHeartRadio**: https://www.iheart.com/podcast-promotion
- **Podcast Index**: https://podcastindex.org (open source directory)

---

## Monitoring & Maintenance

### Regular Checks

1. **Build Logs**: Monitor Netlify builds for audio generation errors
2. **S3 Storage**: Verify new posts are uploading to S3
3. **RSS Feed**: Validate feed remains iTunes-compliant
4. **FeedBurner**: Check analytics for subscriber growth

### Automated Tasks

- **Audio Generation**: Runs on every build, skips existing files
- **Manifest Updates**: Automatic when new posts are generated
- **RSS Feed**: Generated on every Gatsby build
- **Cache Purge**: Cloudflare cache cleared after every build

### Monthly Review

- Review AWS Polly costs (~$1.60/month expected)
- Check S3 storage usage (should remain under 1GB)
- Validate podcast feed in iTunes Podcast Connect
- Monitor download/stream analytics

---

## Lessons Learned

### What Worked Well

1. **S3-First Strategy**: Checking S3 before generation eliminated unnecessary API costs
2. **Text Chunking with Validation**: Multi-level splitting (sentence → word → character) handled all edge cases
3. **Manifest Tracking**: JSON manifest provided single source of truth for audio metadata
4. **Custom Elements Pattern**: Using `custom_elements` with `_attr` format for RSS enclosures
5. **Explicit Type Conversion**: `parseInt(audioSize, 10)` ensured proper RSS serialization

### What Could Be Improved

1. **Duration Calculation**: Currently hardcoded to "00:00:00" - should calculate actual MP3 duration
2. **Audio Quality Check**: No validation that generated MP3 is not corrupted
3. **Error Notifications**: Build failures don't trigger alerts
4. **Transcript Generation**: Could add full transcripts to episode show notes
5. **Chapter Markers**: Could add iTunes chapter markers for long episodes

### Recommendations for Future

1. Add MP3 metadata (ID3 tags) with episode info, artwork, etc.
2. Implement audio duration extraction using ffprobe or similar
3. Add automated RSS feed validation in CI/CD pipeline
4. Consider alternative TTS services (ElevenLabs for higher quality)
5. Implement webhook notifications for new episode publishing

---

## Technical Debt

### Known Issues

1. **Duration Field**: All episodes show `00:00:00` instead of actual duration
   - **Impact**: Low - not required by iTunes, but recommended
   - **Fix**: Add ffprobe to extract MP3 duration during upload

2. **No Audio Validation**: Generated MP3s are not tested for playback
   - **Impact**: Medium - could publish corrupted files
   - **Fix**: Add basic MP3 header validation

3. **Single S3 Bucket**: All audio in one bucket, no CDN
   - **Impact**: Low - S3 is reliable and fast
   - **Fix**: Consider CloudFront distribution for global edge caching

### Future Enhancements

1. **Analytics Integration**: Track episode downloads and listener metrics
2. **Dynamic Intro/Outro**: Programmatically add intro music and outro credits
3. **Voice Customization**: Allow per-episode voice selection
4. **Speed Control**: Generate multiple versions (1.0x, 1.25x, 1.5x)
5. **RSS Chapters**: Add chapter markers for blog post sections

---

## Conclusion

Successfully implemented a complete blog-to-podcast pipeline with:

- **Automated audio generation** using AWS Polly Neural voices
- **Cost-optimized S3 storage** with persistent audio files
- **iTunes-compliant RSS feed** with all required metadata
- **Scalable architecture** that generates only new posts
- **Professional branding** as "Swarm-It by Next Shift Consulting"

The system is production-ready and requires minimal ongoing maintenance. Total monthly cost is approximately $1.60 for new posts, with negligible storage costs.

**Final Status**: ✅ Production Ready

---

## Appendix: Key Files

### Audio Generation Script
- **Path**: `scripts/generate-audio.js`
- **Size**: ~700 lines
- **Key Functions**: `generateAudioWithPolly()`, `splitTextIntoChunks()`, `checkS3FileExists()`

### RSS Feed Configuration
- **Path**: `gatsby-config.mjs`
- **Lines**: 213-420 (gatsby-plugin-feed)
- **Key Sections**: `custom_namespaces`, `custom_elements`, `serialize()`

### Audio Manifest
- **Path**: `static/audio/manifest.json`
- **Entries**: 57 blog posts
- **Format**: JSON with S3 URLs and metadata

### Environment Configuration
- **Development**: `.env.development`
- **Production**: Netlify Environment Variables
- **Required Vars**: AWS credentials, S3 bucket name, Polly voice selection

---

**Document Version**: 1.0
**Last Updated**: March 12, 2026
**Author**: Rudy Martin (with Claude Code assistance)
**Status**: Complete
