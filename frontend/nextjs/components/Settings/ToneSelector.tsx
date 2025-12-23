import React, { ChangeEvent } from 'react';

interface ToneSelectorProps {
  tone: string;
  onToneChange: (event: ChangeEvent<HTMLSelectElement>) => void;
}
export default function ToneSelector({ tone, onToneChange }: ToneSelectorProps) {
  return (
    <div className="form-group">
      <label htmlFor="tone" className="agent_question">语气风格 </label>
      <select 
        name="tone" 
        id="tone" 
        value={tone} 
        onChange={onToneChange} 
        className="form-control-static"
        required
      >
        <option value="Objective">客观 - 公正无偏见地呈现事实和发现</option>
        <option value="Formal">正式 - 遵循学术标准，使用复杂的语言和结构</option>
        <option value="Analytical">分析性 - 对数据和理论进行批判性评估和详细审查</option>
        <option value="Persuasive">说服性 - 让受众信服特定观点或论证</option>
        <option value="Informative">信息性 - 清晰全面地提供主题信息</option>
        <option value="Explanatory">解释性 - 阐明复杂概念和过程</option>
        <option value="Descriptive">描述性 - 详细描述现象、实验或案例研究</option>
        <option value="Critical">批判性 - 判断研究及其结论的有效性和相关性</option>
        <option value="Comparative">比较性 - 对比不同理论、数据或方法以突出差异和相似之处</option>
        <option value="Speculative">推测性 - 探索假设、潜在含义或未来研究方向</option>
        <option value="Reflective">反思性 - 考虑研究过程和个人见解或经验</option>
        <option value="Narrative">叙事性 - 讲述故事以说明研究发现或方法论</option>
        <option value="Humorous">幽默性 - 轻松有趣，通常使内容更易产生共鸣</option>
        <option value="Optimistic">乐观性 - 强调积极发现和潜在益处</option>
        <option value="Pessimistic">悲观性 - 关注局限性、挑战或负面结果</option>
        <option value="Simple">简单性 - 为年轻读者编写，使用基本词汇和清晰解释</option>
        <option value="Casual">随意性 - 对话式和轻松风格，便于日常阅读</option>
      </select>
    </div>
  );
}