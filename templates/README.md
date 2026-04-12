# Templates

Vertical-specific website templates, each a self-contained React/Next.js
component package driven by a `content.schema.json` contract.

## POC scope

Only `movers/` exists for POC. Lawyers and cleaners are deferred.

## Template contract

Every template exports a default React component that accepts a single
`content` prop matching its `content.schema.json`. The Website Builder is
responsible for producing data that conforms to this schema. Missing fields
must degrade gracefully — never crash the render.

## Creating a new template

1. Copy an existing template directory
2. Update `content.schema.json` with the fields your layout needs
3. Update `pipeline/agents/website_builder.py` to map `ExtractionResult` → your schema
4. Add the template to `tailwind.config.ts` content globs if needed
