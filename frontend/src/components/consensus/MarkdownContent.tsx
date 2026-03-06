"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Code,
  Text,
  Title,
  List,
  ListItem,
  Table,
  TableThead,
  TableTbody,
  TableTr,
  TableTh,
  TableTd,
  Blockquote,
  Anchor,
  Divider,
} from "@mantine/core";

interface MarkdownContentProps {
  children: string;
}

export function MarkdownContent({ children }: MarkdownContentProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => (
          <Text size="sm" mb="xs">
            {children}
          </Text>
        ),
        h1: ({ children }) => (
          <Title order={3} mb="xs">
            {children}
          </Title>
        ),
        h2: ({ children }) => (
          <Title order={4} mb="xs">
            {children}
          </Title>
        ),
        h3: ({ children }) => (
          <Title order={5} mb="xs">
            {children}
          </Title>
        ),
        strong: ({ children }) => (
          <Text component="span" fw={700} inherit>
            {children}
          </Text>
        ),
        em: ({ children }) => (
          <Text component="span" fs="italic" inherit>
            {children}
          </Text>
        ),
        code: ({ children, className }) => {
          const isBlock = className?.startsWith("language-");
          if (isBlock) {
            return (
              <Code block mb="xs">
                {children}
              </Code>
            );
          }
          return <Code>{children}</Code>;
        },
        pre: ({ children }) => <>{children}</>,
        ul: ({ children }) => (
          <List size="sm" mb="xs">
            {children}
          </List>
        ),
        ol: ({ children }) => (
          <List type="ordered" size="sm" mb="xs">
            {children}
          </List>
        ),
        li: ({ children }) => <ListItem>{children}</ListItem>,
        blockquote: ({ children }) => (
          <Blockquote mb="xs">{children}</Blockquote>
        ),
        a: ({ href, children }) => (
          <Anchor
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            size="sm"
          >
            {children}
          </Anchor>
        ),
        hr: () => <Divider my="xs" />,
        table: ({ children }) => (
          <Table mb="xs" striped highlightOnHover>
            {children}
          </Table>
        ),
        thead: ({ children }) => <TableThead>{children}</TableThead>,
        tbody: ({ children }) => <TableTbody>{children}</TableTbody>,
        tr: ({ children }) => <TableTr>{children}</TableTr>,
        th: ({ children }) => <TableTh>{children}</TableTh>,
        td: ({ children }) => <TableTd>{children}</TableTd>,
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
