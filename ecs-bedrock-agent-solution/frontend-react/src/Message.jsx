import React from 'react';
import { Container, ExpandableSection, Box } from '@cloudscape-design/components';
import { parseMessageContent, generateJSONSummary } from './markdown';

export default function Message({ role, content, structuredData, humanSummary }) {
  const { html, jsonSections } = parseMessageContent(content);
  const parts = html.split(/<!--JSON_SECTION_(\d+)-->/);

  return (
    <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: '50%',
          background: role === 'user' ? '#FF9900' : '#232F3E',
          color: '#fff',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          fontSize: 16,
        }}
      >
        {role === 'user' ? '👤' : '🛡️'}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <Container variant={role === 'user' ? 'default' : 'stacked'}>
          {parts.map((part, i) =>
            i % 2 === 0 ? (
              <div key={`text-${i}`} dangerouslySetInnerHTML={{ __html: part }} />
            ) : (
              <ExpandableSection
                key={`json-${part}`}
                headerText="📊 Analysis Results"
                variant="footer"
              >
                <div
                  dangerouslySetInnerHTML={{
                    __html: jsonSections[Number(part)]?.summary || '',
                  }}
                />
                <Box margin={{ top: 's' }}>
                  <ExpandableSection headerText="Raw JSON" variant="footer">
                    <pre style={{ fontSize: 12, overflow: 'auto' }}>
                      {JSON.stringify(jsonSections[Number(part)]?.data, null, 2)}
                    </pre>
                  </ExpandableSection>
                </Box>
              </ExpandableSection>
            )
          )}

          {structuredData && (
            <Box margin={{ top: 's' }}>
              <ExpandableSection headerText="📊 Detailed Results" variant="footer">
                <div
                  dangerouslySetInnerHTML={{
                    __html: humanSummary || generateJSONSummary(structuredData),
                  }}
                />
                <Box margin={{ top: 's' }}>
                  <ExpandableSection headerText="Raw JSON" variant="footer">
                    <pre style={{ fontSize: 12, overflow: 'auto' }}>
                      {JSON.stringify(structuredData, null, 2)}
                    </pre>
                  </ExpandableSection>
                </Box>
              </ExpandableSection>
            </Box>
          )}
        </Container>
      </div>
    </div>
  );
}
