import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Container,
  SpaceBetween,
  Input,
  Button,
  Box,
  StatusIndicator,
  Alert,
  ButtonDropdown,
} from '@cloudscape-design/components';
import { sendChat } from './api';
import Message from './Message';

const WELCOME = `# Welcome to the AWS Well-Architected Security Assistant! 🛡️

I can help you analyze your AWS security posture.

## Quick Actions:
- **"Check my security services"** — Verify enabled security services
- **"What are my security findings?"** — Review security issues
- **"Analyze my storage encryption"** — Check data protection at rest
- **"Review my network security"** — Examine data protection in transit`;

let msgCounter = 0;

export default function ChatPage({ user }) {
  const [messages, setMessages] = useState([
    { id: ++msgCounter, role: 'assistant', content: WELCOME },
  ]);
  const [input, setInput] = useState('');
  const [awsAccountId, setAwsAccountId] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = useCallback(async (text) => {
    const msg = (text || input).trim();
    if (!msg) return;
    setInput('');
    setError('');
    setMessages((prev) => [...prev, { id: ++msgCounter, role: 'user', content: msg }]);
    setSending(true);
    try {
      const data = await sendChat(msg, awsAccountId);
      setMessages((prev) => [
        ...prev,
        {
          id: ++msgCounter,
          role: 'assistant',
          content: data.response || 'Analysis completed.',
          structuredData: data.structured_data,
          humanSummary: data.human_summary,
        },
      ]);
    } catch {
      setError('Failed to send message. Please try again.');
      setMessages((prev) => [
        ...prev,
        { id: ++msgCounter, role: 'assistant', content: 'Sorry, I encountered an error. Please try again.' },
      ]);
    } finally {
      setSending(false);
    }
  }, [input, awsAccountId]);

  const quickActions = [
    { id: '1', text: 'Security Services' },
    { id: '2', text: 'Security Findings' },
    { id: '3', text: 'Storage Encryption' },
  ];
  const quickMap = {
    '1': 'Check my security services',
    '2': 'What are my security findings?',
    '3': 'Analyze my storage encryption',
  };

  return (
    <SpaceBetween size="m">
      {/* Toolbar — user info / logout already in TopNavigation (App.jsx) */}
      <Container>
        <SpaceBetween direction="horizontal" size="m" alignItems="center">
          <StatusIndicator type="success">Connected</StatusIndicator>
          <Input
            value={awsAccountId}
            onChange={({ detail }) => setAwsAccountId(detail.value)}
            placeholder="AWS Account ID"
            type="text"
            inputMode="numeric"
          />
          <ButtonDropdown
            items={quickActions}
            onItemClick={({ detail }) => send(quickMap[detail.id])}
          >
            Quick Actions
          </ButtonDropdown>
          <Button onClick={() => setMessages([])}>Clear Chat</Button>
        </SpaceBetween>
      </Container>

      {/* Messages */}
      <div style={{ height: 'calc(100vh - 280px)', overflowY: 'auto', padding: '0 4px' }}>
        {messages.map((m) => (
          <Message key={m.id} {...m} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <SpaceBetween direction="horizontal" size="xs">
        <div style={{ flex: 1 }}>
          <Input
            value={input}
            onChange={({ detail }) => setInput(detail.value)}
            placeholder="Ask about your AWS security posture..."
            onKeyDown={({ detail }) => {
              if (detail.key === 'Enter') send();
            }}
            disabled={sending}
          />
        </div>
        <Button variant="primary" loading={sending} onClick={() => send()}>
          Send
        </Button>
      </SpaceBetween>

      {error && <Alert type="error" dismissible onDismiss={() => setError('')}>{error}</Alert>}

      <Alert type="info">
        <a
          href="https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/create/review?templateURL=https://workshop-data-public.s3.ap-northeast-1.amazonaws.com/remote-role-mcpreadonlyall-20250831_134154.yaml&stackName=remote-mcp-readonly-role&capabilities=CAPABILITY_IAM"
          target="_blank"
          rel="noreferrer"
        >
          Deploy a ReadOnly IAM Role
        </a>{' '}
        to allow the assistant to scan your AWS environment.
      </Alert>
    </SpaceBetween>
  );
}
